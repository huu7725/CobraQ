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

## Retrieval gold CSV

Each query must be judged against the corpus independently of system output.
`relevant_chunk_ids` uses semicolon-separated IDs. Do not infer relevance from
whether the system cited or blocked a chunk.

## Student responses CSV

Long format with one row per student/item and the columns
`student_id,item_id,is_correct`. Use pseudonymous student IDs.
