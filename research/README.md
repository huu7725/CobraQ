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

Build the reproducible 600-item annotation candidate set from the reviewed
corpus:

```powershell
python research/build_aqg_candidates.py
```

Review `outputs/cobraq_aqg_review/CobraQ_AQG_600_Review.xlsx`. Source and draft
columns are integrity-checked; teacher edits belong only in the `teacher_*`
columns. Complete the nine rubric criteria, decision, factual-error flag,
reviewer ID, and review date in `DANH_GIA`.

Validate progress without writing training data:

```powershell
python research/finalize_aqg_dataset.py `
  --workbook outputs/cobraq_aqg_review/CobraQ_AQG_600_Review.xlsx
```

After the rubric gates pass, export teacher-approved train/validation/test
splits:

```powershell
python research/finalize_aqg_dataset.py `
  --workbook outputs/cobraq_aqg_review/CobraQ_AQG_600_Review.xlsx --apply
```

Splits are grouped by source chunk within each lesson so evidence used for
training cannot reappear in validation or test.

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
python research/train_lora.py --train data/research/aqg_v1/approved/train.jsonl `
  --validation data/research/aqg_v1/approved/validation.jsonl --qlora `
  --max-length 1792 --batch-size 1 --save-steps 10 `
  --resume-from-checkpoint auto
```

The training script stops when CUDA is unavailable unless `--allow-cpu` is used
for a smoke test. The completed local QLoRA run used an RTX 3050 Ti Laptop GPU,
480/60 reviewed train/validation examples, three epochs, and 3.076 MB peak VRAM.
Its manifest is `artifacts/adapters/history12_lora/training_manifest.json`.

Verify adapter loading and one held-out generation:

```powershell
python research/verify_adapter.py --index 0 --max-new-tokens 1024
```

The report is written to
`artifacts/adapters/history12_lora/verification_report.json`. A valid JSON result
is necessary but not sufficient: schema, citation, factuality and teacher gates
still apply.

## 3. Run C0-C3

```powershell
python research/run_experiments.py --backend local --continue-on-error
```

Use a one-request infrastructure pilot before the full run:

```powershell
python research/run_experiments.py --backend local --limit 1 `
  --continue-on-error --output data/research/experiment_pilot_1.jsonl
```

- C0: base SLM.
- C1: base SLM + RAG.
- C2: LoRA SLM.
- C3: LoRA SLM + RAG.

The runner writes one JSONL record per request/condition plus a summary containing
success/error rates, error types, fact support, automatic verification rate, and
p50/p95 latency. A failed schema generation is an experimental result and must not
be silently removed from the denominator.

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
- Near-duplicate multiple-choice options are rejected before Trust Layer review.
- Dates/years in the stem, correct answer, and explanation must exist in evidence.
- Evidence with pending OCR review forces `needs_teacher_review`.
- Every student-facing question must have status `teacher_approved`.
- BLEU/ROUGE/BERTScore are secondary; factuality and blinded teacher scores are
  primary outcomes.
