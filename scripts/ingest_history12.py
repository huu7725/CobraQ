"""Build the CobraQ Grade 12 History corpus from the scanned textbook PDF.

The command performs local OCR with Tesseract, writes page-level audit files,
creates traceable semantic chunks, and can index them into ChromaDB.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.history_corpus import (  # noqa: E402
    HistoryChunk,
    chunk_page_text,
    load_book_config,
    write_jsonl,
)


DEFAULT_PDF = ROOT / "file doc" / "SGK Lịch sử 12 Kết nối tri thức.pdf"
DEFAULT_CONFIG = ROOT / "research" / "configs" / "history12_kntt.json"
DEFAULT_OUTPUT = ROOT / "data" / "research" / "history12_kntt"
DEFAULT_TESSDATA = ROOT / "tools" / "tessdata"
WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEFAULT_TESSERACT = Path(
    shutil.which("tesseract")
    or (str(WINDOWS_TESSERACT) if WINDOWS_TESSERACT.exists() else "tesseract")
)
DEFAULT_PDFTOPPM = Path(shutil.which("pdftoppm") or "pdftoppm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--pages", help="PDF pages, e.g. 8-20 or 8,10,12")
    parser.add_argument("--force", action="store_true", help="Re-run OCR for existing pages")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--embedding-model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--collection", default="cobraq_history12_kntt_v1")
    parser.add_argument("--tesseract", type=Path, default=DEFAULT_TESSERACT)
    parser.add_argument("--tessdata", type=Path, default=DEFAULT_TESSDATA)
    parser.add_argument("--pdftoppm", type=Path, default=DEFAULT_PDFTOPPM)
    return parser.parse_args()


def resolve_pages(spec: str | None, start: int, end: int) -> list[int]:
    if not spec:
        return list(range(start, end + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            pages.update(range(int(left), int(right) + 1))
        else:
            pages.add(int(part))
    invalid = [page for page in pages if page < start or page > end]
    if invalid:
        raise ValueError(f"Pages outside configured content range {start}-{end}: {invalid}")
    return sorted(pages)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_tsv(path: Path) -> tuple[str, float | None, int]:
    paragraphs: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    confidences: list[float] = []
    word_count = 0
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            value = (row.get("text") or "").strip()
            if not value or row.get("level") != "5":
                continue
            block = int(row.get("block_num") or 0)
            paragraph = int(row.get("par_num") or 0)
            line = int(row.get("line_num") or 0)
            word = int(row.get("word_num") or 0)
            paragraphs.setdefault((block, paragraph), []).append((line, word, value))
            word_count += 1
            try:
                confidence = float(row.get("conf") or -1)
                if confidence >= 0:
                    confidences.append(confidence)
            except ValueError:
                pass

    blocks: list[str] = []
    for key in sorted(paragraphs):
        words = sorted(paragraphs[key], key=lambda item: (item[0], item[1]))
        lines: dict[int, list[str]] = {}
        for line, _, value in words:
            lines.setdefault(line, []).append(value)
        paragraph_text = "\n".join(" ".join(lines[index]) for index in sorted(lines))
        if paragraph_text.strip():
            blocks.append(paragraph_text.strip())
    confidence = round(sum(confidences) / len(confidences), 2) if confidences else None
    return "\n\n".join(blocks), confidence, word_count


def run_checked(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if process.returncode:
        detail = (process.stderr or process.stdout).strip()
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(command)}\n{detail}")


def ocr_page(
    page: int,
    *,
    pdf: Path,
    output_dir: Path,
    pdftoppm: Path,
    tesseract: Path,
    tessdata: Path,
    dpi: int,
    force: bool,
) -> dict[str, Any]:
    pages_dir = output_dir / "ocr" / "pages"
    tsv_dir = output_dir / "ocr" / "tsv"
    pages_dir.mkdir(parents=True, exist_ok=True)
    tsv_dir.mkdir(parents=True, exist_ok=True)
    text_path = pages_dir / f"page_{page:03d}.txt"
    tsv_path = tsv_dir / f"page_{page:03d}.tsv"

    started = time.perf_counter()
    cached = not force and text_path.exists() and tsv_path.exists()
    selected_psm = 3
    if cached:
        text, confidence, word_count = parse_tsv(tsv_path)
        if not text_path.read_text(encoding="utf-8").strip():
            text_path.write_text(text, encoding="utf-8", newline="\n")

    needs_ocr = not cached
    needs_repair = cached and (word_count < 180 or (confidence is not None and confidence < 80))
    if needs_ocr or needs_repair:
        with tempfile.TemporaryDirectory(prefix=f"cobraq_ocr_{page:03d}_") as temp_name:
            temp_dir = Path(temp_name)
            image_base = temp_dir / f"page_{page:03d}"
            run_checked(
                [
                    str(pdftoppm), "-f", str(page), "-l", str(page), "-singlefile",
                    "-png", "-r", str(dpi), str(pdf), str(image_base),
                ]
            )
            image_path = image_base.with_suffix(".png")
            candidates = []
            psm_values = (3,) if needs_ocr else ()
            for psm in psm_values:
                ocr_base = temp_dir / f"ocr_{page:03d}_psm{psm}"
                run_checked(
                    [
                        str(tesseract), str(image_path), str(ocr_base), "-l", "vie+eng",
                        "--tessdata-dir", str(tessdata), "--psm", str(psm), "tsv",
                    ]
                )
                generated_tsv = ocr_base.with_suffix(".tsv")
                candidate_text, candidate_confidence, candidate_words = parse_tsv(generated_tsv)
                candidates.append((psm, candidate_text, candidate_confidence, candidate_words, generated_tsv))

            if cached:
                cached_copy = temp_dir / f"cached_{page:03d}.tsv"
                shutil.copy2(tsv_path, cached_copy)
                candidates.append((3, text, confidence, word_count, cached_copy))

            initial_best = max(
                candidates,
                key=lambda item: item[3] * max(item[2] or 0.0, 50.0) / 100.0,
            )
            if initial_best[3] < 180 or (initial_best[2] is not None and initial_best[2] < 80):
                for psm in (6, 11):
                    ocr_base = temp_dir / f"ocr_{page:03d}_psm{psm}"
                    run_checked(
                        [
                            str(tesseract), str(image_path), str(ocr_base), "-l", "vie+eng",
                            "--tessdata-dir", str(tessdata), "--psm", str(psm), "tsv",
                        ]
                    )
                    generated_tsv = ocr_base.with_suffix(".tsv")
                    candidate_text, candidate_confidence, candidate_words = parse_tsv(generated_tsv)
                    candidates.append((psm, candidate_text, candidate_confidence, candidate_words, generated_tsv))

            selected_psm, text, confidence, word_count, generated_tsv = max(
                candidates,
                key=lambda item: item[3] * max(item[2] or 0.0, 50.0) / 100.0,
            )
            text_path.write_text(text, encoding="utf-8", newline="\n")
            shutil.copy2(generated_tsv, tsv_path)

    elapsed = round(time.perf_counter() - started, 3)
    return {
        "pdf_page": page,
        "text_path": text_path.relative_to(output_dir).as_posix(),
        "tsv_path": tsv_path.relative_to(output_dir).as_posix(),
        "ocr_confidence": confidence,
        "ocr_psm": selected_psm,
        "word_count": word_count,
        "char_count": len(text_path.read_text(encoding="utf-8")),
        "elapsed_seconds": elapsed,
    }


def build_chunks(
    page_records: list[dict[str, Any]],
    *,
    output_dir: Path,
    config: dict[str, Any],
) -> list[HistoryChunk]:
    chunks: list[HistoryChunk] = []
    source = config["book"]["title"] + " - " + config["book"]["series"]
    for record in sorted(page_records, key=lambda item: item["pdf_page"]):
        text = (output_dir / record["text_path"]).read_text(encoding="utf-8")
        chunks.extend(
            chunk_page_text(
                text,
                pdf_page=record["pdf_page"],
                config=config,
                source=source,
                ocr_confidence=record["ocr_confidence"],
            )
        )
    return chunks


def index_chunks(
    chunks: list[HistoryChunk],
    *,
    output_dir: Path,
    collection: str,
    embedding_model: str,
) -> dict[str, Any]:
    from app.services.trust_layer import Chunk
    from app.services.vector_service import VectorService

    service = VectorService(
        persist_dir=str(output_dir / "chroma_db"),
        collection_name=collection,
        embedding_model=embedding_model,
    )
    retrieval_chunks = [
        Chunk(
            id=item.chunk_id,
            text=item.text,
            source=item.source,
            page=item.book_page,
            score=0.0,
            metadata={
                "book_id": item.book_id,
                "grade": item.grade,
                "series": item.series,
                "pdf_page": item.pdf_page,
                "book_page": item.book_page,
                "topic_id": item.topic_id,
                "topic_title": item.topic_title,
                "lesson_id": item.lesson_id,
                "lesson_number": item.lesson_number or 0,
                "lesson_title": item.lesson_title,
                "section_title": item.section_title,
                "segment_type": item.segment_type,
                "time_expressions": item.time_expressions,
                "entity_candidates": item.entity_candidates,
                "review_required": item.review_required,
                "ocr_review_status": item.ocr_review_status,
            },
        )
        for item in chunks
    ]
    doc_id = configured_doc_id(chunks)
    service.delete_doc(doc_id)
    service.upsert_chunks(doc_id, retrieval_chunks)
    return service.get_stats()


def configured_doc_id(chunks: list[HistoryChunk]) -> str:
    return chunks[0].book_id if chunks else "history12_kntt"


def summarize(chunks: list[HistoryChunk], page_records: list[dict[str, Any]]) -> dict[str, Any]:
    by_topic: dict[str, int] = {}
    by_lesson: dict[str, int] = {}
    for chunk in chunks:
        by_topic[chunk.topic_id] = by_topic.get(chunk.topic_id, 0) + 1
        key = chunk.lesson_id or chunk.topic_id
        by_lesson[key] = by_lesson.get(key, 0) + 1
    confidences = [record["ocr_confidence"] for record in page_records if record["ocr_confidence"] is not None]
    return {
        "pages": len(page_records),
        "chunks": len(chunks),
        "review_required_chunks": sum(chunk.review_required for chunk in chunks),
        "average_ocr_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        "chunks_by_topic": by_topic,
        "chunks_by_lesson": by_lesson,
    }


def main() -> int:
    args = parse_args()
    config = load_book_config(args.config)
    start = int(config["page_mapping"]["content_pdf_start"])
    end = int(config["page_mapping"]["content_pdf_end"])
    pages = resolve_pages(args.pages, start, end)

    for required, label in (
        (args.pdf, "PDF"), (args.config, "config"), (args.tesseract, "Tesseract"),
        (args.tessdata / "vie.traineddata", "Vietnamese OCR model"),
        (args.pdftoppm, "pdftoppm"),
    ):
        if not required.exists():
            raise FileNotFoundError(f"{label} not found: {required}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[ingest] OCR {len(pages)} pages with {args.workers} workers", flush=True)
    page_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                ocr_page,
                page,
                pdf=args.pdf,
                output_dir=args.output_dir,
                pdftoppm=args.pdftoppm,
                tesseract=args.tesseract,
                tessdata=args.tessdata,
                dpi=args.dpi,
                force=args.force,
            ): page
            for page in pages
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            page = futures[future]
            record = future.result()
            page_records.append(record)
            print(
                f"[ingest] {completed:03d}/{len(pages):03d} page={page:03d} "
                f"conf={record['ocr_confidence']} words={record['word_count']}",
                flush=True,
            )

    page_records.sort(key=lambda item: item["pdf_page"])
    chunks = build_chunks(page_records, output_dir=args.output_dir, config=config)
    corpus_path = args.output_dir / "chunks.jsonl"
    write_jsonl((chunk.to_dict() for chunk in chunks), corpus_path)

    summary = summarize(chunks, page_records)
    manifest = {
        "schema_version": "1.0",
        "source": {
            "path": str(args.pdf.resolve()),
            "sha256": file_sha256(args.pdf),
            **config["book"],
        },
        "ocr": {
            "engine": "Tesseract 5.4",
            "languages": ["vie", "eng"],
            "dpi": args.dpi,
            "psm_primary": 3,
            "psm_fallback": [6, 11],
            "fallback_trigger": "word_count < 180 or confidence < 80",
        },
        "pages": page_records,
        "summary": summary,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    if not args.skip_index and chunks:
        print(f"[ingest] indexing {len(chunks)} chunks with {args.embedding_model}", flush=True)
        summary["vector_store"] = index_chunks(
            chunks,
            output_dir=args.output_dir,
            collection=args.collection,
            embedding_model=args.embedding_model,
        )
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
