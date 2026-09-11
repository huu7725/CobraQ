from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.aqg_prompt import (  # noqa: E402
    PROMPT_CONTRACT_VERSION,
    build_aqg_messages,
    serialize_chat_messages,
    training_messages,
)


class PromptBuilderTests(unittest.TestCase):
    def test_question_type_rules_are_isolated(self):
        mcq = build_aqg_messages(
            question_type="multiple_choice",
            instruction="Sinh một câu hỏi kiểm tra.",
        )[1]["content"]
        essay = build_aqg_messages(
            question_type="short_essay",
            instruction="Sinh một câu hỏi kiểm tra.",
        )[1]["content"]

        self.assertEqual(PROMPT_CONTRACT_VERSION, "2.1")
        self.assertIn("MCQ: question_type=multiple_choice", mcq)
        self.assertNotIn("choices=[]", mcq)
        self.assertIn("Tự luận: question_type=short_essay; choices=[]", essay)
        self.assertNotIn("MCQ:", essay)

    def test_empty_context_is_omitted_instead_of_replaced(self):
        content = build_aqg_messages(
            question_type="multiple_choice",
            instruction="Sinh một câu hỏi kiểm tra.",
            context="",
        )[1]["content"]
        self.assertNotIn("Ngữ liệu SGK", content)
        self.assertNotIn("Không cung cấp ngữ liệu truy xuất", content)

    def test_rag_context_is_present(self):
        content = build_aqg_messages(
            question_type="short_essay",
            instruction="Sinh một câu hỏi kiểm tra.",
            context="Năm 1945, nước Việt Nam Dân chủ Cộng hòa ra đời.",
        )[1]["content"]
        self.assertIn("nguồn dữ kiện duy nhất", content)
        self.assertIn("Năm 1945", content)

    def test_training_and_runtime_builder_contract_match(self):
        record = {
            "instruction": "Sinh một câu hỏi kiểm tra.",
            "context": "Dữ kiện SGK đã duyệt.",
            "response": {"questions": [{"question_type": "short_essay"}]},
        }
        self.assertEqual(
            training_messages(record),
            build_aqg_messages(
                question_type="short_essay",
                instruction=record["instruction"],
                context=record["context"],
            ),
        )

    def test_native_chat_template_is_required_and_used(self):
        class FakeTokenizer:
            chat_template = "native-template"

            def __init__(self):
                self.call = None

            def apply_chat_template(self, messages, **kwargs):
                self.call = (messages, kwargs)
                return "<native-chat-prompt>"

        tokenizer = FakeTokenizer()
        messages = build_aqg_messages(
            question_type="multiple_choice",
            instruction="Sinh một câu hỏi kiểm tra.",
        )
        self.assertEqual(
            serialize_chat_messages(tokenizer, messages),
            "<native-chat-prompt>",
        )
        self.assertEqual(tokenizer.call[0], messages)
        self.assertEqual(
            tokenizer.call[1],
            {"tokenize": False, "add_generation_prompt": True},
        )

        tokenizer.chat_template = None
        with self.assertRaisesRegex(ValueError, "no chat_template"):
            serialize_chat_messages(tokenizer, messages)


if __name__ == "__main__":
    unittest.main()
