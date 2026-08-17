# Research dataset contracts

## AQG LoRA JSONL

Required fields:

- `record_id`
- `lesson_id`
- `instruction`
- `context`
- `response`: JSON string or object following the CobraQ question schema
- `source_chunk_ids`
- `review_status`: must be `teacher_approved`
- `reviewer_id`

The training command rejects records without `teacher_approved` status.

### AQG 600-sample annotation workflow

1. Run `python research/build_aqg_candidates.py` to create deterministic,
   source-grounded candidates with `pending_teacher_review` status.
2. Review and, where needed, rewrite every item in
   `outputs/cobraq_aqg_review/CobraQ_AQG_600_Review.xlsx`.
3. Run `python research/finalize_aqg_dataset.py --workbook <path>` to validate
   progress. Add `--apply` only after accepted rows satisfy the teacher rubric.
4. The finalizer exports train/validation/test splits grouped by source chunk,
   preventing the same textbook evidence from leaking across splits.

## Retrieval gold CSV

Each query must be judged against the corpus independently of system output.
`relevant_chunk_ids` uses semicolon-separated IDs. Do not infer relevance from
whether the system cited or blocked a chunk.

## Student responses CSV

Long format with one row per student/item and the columns
`student_id,item_id,is_correct`. Use pseudonymous student IDs.
