# CobraQ Research Pipeline

This directory contains the reproducible research workflow for the Grade 12
History Auto-Exam system. The operational demo and the C0-C3 experiments share
the same corpus and output schema.

## Frozen scope

- Textbook: `Lịch sử 12 - Kết nối tri thức với cuộc sống`.
- Content: 6 topics, 17 lessons, glossary, and transcription table.
- Corpus config: `research/configs/history12_kntt.json`.
- Ablation config: `research/configs/experiments.json`.
- Teacher rubric: `research/rubrics/teacher_rubric.json`.

The textbook PDF and derived OCR corpus are local research data and are excluded
from Git. Do not redistribute the textbook or OCR output without permission.

## 1. Build the corpus

Prerequisites:

- Tesseract 5 with local `vie` and `eng` trained data.
- Poppler `pdftoppm`.
- Python dependencies from `backend/requirements.txt`.

Run:

```powershell
python scripts/ingest_history12.py --output-dir data/research/history12_kntt
```

Outputs:

- `ocr/pages/`: page text for source audit.
- `ocr/tsv/`: word boxes and confidence values.
- `chunks.jsonl`: traceable RAG units.
- `manifest.json`: source SHA-256 and OCR parameters.
- `summary.json`: page/chunk coverage.
- `chroma_db/`: multilingual vector index.

Low-coverage pages are retried with PSM 6 and 11. Suspicious chunks remain
searchable but cannot receive `auto_verified` status before human review.

Create the OCR review queue:

```powershell
python research/build_ocr_review_queue.py
```

Prepare the teacher-review workbook and render the 55 source pages referenced by
the queue:

```powershell
python research/prepare_ocr_review.py
```

Open `outputs/cobraq_ocr_review/CobraQ_OCR_Review.xlsx`. Reviewers must fill in
`review_status`, `corrected_text` when needed, `reviewer_id`, `review_date`, and
`review_comment`. The risk priority is technical pre-triage only and is never
treated as teacher approval.

Check progress without changing the corpus:

```powershell
python research/apply_ocr_review.py
```

After all 61 rows have been reviewed, create a separate reviewed corpus and
immutable audit log:

```powershell
python research/apply_ocr_review.py --apply --reindex
```

The command refuses to apply when a row is pending, the source text was edited,
a correction is empty, or reviewer identity/date is missing. The raw
`chunks.jsonl` is never overwritten.
Restart the API after reindexing so all cached pipeline state uses the reviewed
collection.

## 2. Prepare AQG requests and LoRA data

Generate a deterministic set of 40 lesson-balanced requests:

```powershell
python research/build_eval_requests.py
```

LoRA training JSONL requires `instruction`, optional `context`, and `response`.
Every response must be valid CobraQ question JSON and teacher-reviewed. Split
train/validation/test by lesson or content cluster, not random question rows.

Install GPU research dependencies and train:

```powershell
pip install -r requirements-research.txt
python research/train_lora.py --train research/datasets/train.jsonl `
  --validation research/datasets/validation.jsonl --qlora
```

The training script stops when CUDA is unavailable unless `--allow-cpu` is used
for a smoke test. The current machine is CPU-only, so it cannot produce the final
LoRA adapter in a practical time.

## 3. Run C0-C3

```powershell
python research/run_experiments.py --backend local --continue-on-error
```

- C0: base SLM.
- C1: base SLM + RAG.
- C2: LoRA SLM.
- C3: LoRA SLM + RAG.

The runner writes one JSONL record per request/condition plus a summary containing
fact support, automatic verification rate, and p50/p95 latency.

## 4. Teacher and student evaluation

Teachers use `research/rubrics/teacher_scoring_template.csv` in a blinded review.
After unblinding, compute weighted scores with:

```powershell
python research/score_teacher_rubric.py path/to/teacher_scores.csv
```

Student response CSV uses long format: `student_id,item_id,is_correct`.

```powershell
python research/analyze_student_items.py path/to/student_responses.csv
```

The report includes item difficulty, point-biserial discrimination, Cronbach's
alpha, and a warning when the student sample is below 100.

Capture the exact runtime before training/evaluation:

```powershell
python research/capture_environment.py
```

## 5. API

- `GET /api/research/config`
- `GET /api/research/corpus/stats`
- `POST /api/research/search`
- `POST /api/research/generate`

Set these environment variables for local SLM deployment:

- `COBRAQ_MODEL_BACKEND=local`
- `COBRAQ_BASE_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- `COBRAQ_ADAPTER_PATH=artifacts/adapters/history12_lora`
- `COBRAQ_CORPUS_DIR=data/research/history12_kntt`

The API backend is retained only as a development/reference baseline. Research
claims about SLM cost and latency must use the local backend.

## 6. Quality gates

- RAG questions require valid chunk citations and exact source quotes.
- Dates/years in the stem, correct answer, and explanation must exist in evidence.
- Evidence with pending OCR review forces `needs_teacher_review`.
- Every student-facing question must have status `teacher_approved`.
- BLEU/ROUGE/BERTScore are secondary; factuality and blinded teacher scores are
  primary outcomes.
