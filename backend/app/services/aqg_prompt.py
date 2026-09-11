"""Shared AQG v2.1 prompt contract for training, verification, and runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal


PROMPT_CONTRACT_VERSION = "2.1"
QuestionType = Literal["multiple_choice", "short_essay"]
ChatMessage = dict[str, str]

SYSTEM_MESSAGE = (
    "Sinh câu hỏi Lịch sử 12. Chỉ trả JSON hợp lệ, không Markdown hay văn bản ngoài JSON."
)

COMMON_RULES = (
    "JSON chỉ có questions với đúng số câu. Mỗi câu chỉ gồm question_type, stem, "
    "choices, correct_answer, explanation. Không sinh ID, metadata hay citation. "
    "Không bịa ngày tháng, nhân vật, địa điểm hoặc quan hệ nguyên nhân-kết quả."
)

TYPE_RULES = {
    "multiple_choice": (
        "MCQ: question_type=multiple_choice; choices gồm đúng 4 object {label,text} "
        "theo A,B,C,D, nội dung không trùng; correct_answer là một nhãn A-D và chỉ "
        "một đáp án đúng; explanation dựa trên dữ kiện."
    ),
    "short_essay": (
        "Tự luận: question_type=short_essay; choices=[]; correct_answer là đáp án mẫu "
        "hoặc ý chính tối thiểu; explanation nêu căn cứ lịch sử và yêu cầu lập luận."
    ),
}


def build_aqg_messages(
    *,
    question_type: QuestionType,
    instruction: str,
    context: str = "",
) -> list[ChatMessage]:
    """Build the only prompt message shape allowed by the AQG v2.1 pipeline."""
    if question_type not in TYPE_RULES:
        raise ValueError(f"Unsupported question_type: {question_type!r}")
    request = instruction.strip()
    if not request:
        raise ValueError("AQG instruction must not be empty")

    sections = [
        f"Yêu cầu:\n{request}",
        f"Đầu ra:\n{COMMON_RULES}",
        TYPE_RULES[question_type],
    ]
    evidence = context.strip()
    if evidence:
        sections.append(
            "Ngữ liệu SGK (nguồn dữ kiện duy nhất):\n" + evidence
        )
        sections.append("Mọi dữ kiện phải được ngữ liệu hỗ trợ.")
    return [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": "\n\n".join(sections)},
    ]


def serialize_chat_messages(
    tokenizer: Any,
    messages: Sequence[Mapping[str, str]],
    *,
    add_generation_prompt: bool = True,
) -> str:
    """Serialize messages with the model-native chat template, never a manual wrapper."""
    if not getattr(tokenizer, "chat_template", None):
        raise ValueError("Tokenizer has no chat_template; AQG v2.1 requires one")
    rendered = tokenizer.apply_chat_template(
        [dict(message) for message in messages],
        tokenize=False,
        add_generation_prompt=add_generation_prompt,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("Tokenizer chat_template returned an empty prompt")
    return rendered


def question_type_from_response(response: object) -> QuestionType:
    """Read the teacher-approved target type without relying on free-form instruction text."""
    payload = json_response(response)
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) != 1:
        raise ValueError("Training response must contain exactly one question")
    question_type = questions[0].get("question_type") if isinstance(questions[0], dict) else None
    if question_type not in TYPE_RULES:
        raise ValueError(f"Unsupported training question_type: {question_type!r}")
    return question_type


def json_response(response: object) -> dict[str, Any]:
    if isinstance(response, str):
        import json

        parsed = json.loads(response)
    else:
        parsed = response
    if not isinstance(parsed, dict):
        raise ValueError("AQG response must be a JSON object")
    return parsed


def training_messages(record: Mapping[str, Any]) -> list[ChatMessage]:
    return build_aqg_messages(
        question_type=question_type_from_response(record.get("response")),
        instruction=str(record.get("instruction") or ""),
        context=str(record.get("context") or ""),
    )
