"""
MRC Service - Machine Reading Comprehension.
Sử dụng LLM (Gemini) để đọc câu hỏi trắc nghiệm và chọn đáp án đúng.
"""

import json
import re
import logging
import os
from typing import Dict, List, Optional

# Try new google.genai package first, fallback to old google.generativeai
HAS_GENAI_NEW = False
HAS_GENAI_OLD = False

try:
    from google import genai
    from google.genai import types
    HAS_GENAI_NEW = True
except ImportError:
    try:
        import google.generativeai as genai
        HAS_GENAI_OLD = True
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# Prompt template cho MRC
MRC_PROMPT_TEMPLATE = """Bạn là chuyên gia môn {subject}. Hãy đọc câu hỏi trắc nghiệm và chọn đáp án ĐÚNG NHẤT.

**Câu hỏi:**
{question}

**Phương án:**
{choices_text}

{context_section}

**Hướng dẫn:**
1. Phân tích kỹ câu hỏi và từng phương án
2. Loại trừ các phương án sai rõ ràng
3. Chọn phương án đúng nhất theo kiến thức môn học
4. Nếu không chắc, chọn phương án khả dĩ nhất

**ĐỊNH DẠNG TRẢ LỜI (JSON):**
Chỉ trả về JSON, không thêm text khác:
{{
  "answer": "A|B|C|D",
  "confidence": 0.0-1.0,
  "explanation": "Giải thích ngắn gọn tại sao chọn đáp án này (1-2 câu)",
  "reasoning": "Suy luận từng bước"
}}

Ví dụ:
{{
  "answer": "B",
  "confidence": 0.92,
  "explanation": "Phương án B đúng vì hàm số thực có miền xác định là tập các số thực.",
  "reasoning": "Hàm số thực f: R → R chỉ xác định với mọi số thực, nên miền là R."
}}"""

class MRCService:
    """
    Machine Reading Comprehension service.
    Sử dụng LLM (Gemini) để đọc và hiểu câu hỏi trắc nghiệm.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.3,
        max_output_tokens: int = 1024
    ):
        """
        Khởi tạo MRCService.

        Args:
            api_key: Google API key
            model_name: Tên model Gemini (gemini-2.0-flash, gemini-1.5-flash, gemini-2.0-flash-exp)
            temperature: Độ ngẫu nhiên (0.0-1.0). Thấp hơn = chắc chắn hơn
            max_output_tokens: Giới hạn output tokens
        """
        if not HAS_GENAI_NEW and not HAS_GENAI_OLD:
            raise ImportError("Thiếu thư viện google-genai. Cài: pip install google-genai")

        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        # Configure API
        if HAS_GENAI_NEW:
            self.client = genai.Client(api_key=api_key)
            logger.info(f"MRCService initialized with google.genai, model: {model_name}")
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"MRCService initialized with google.generativeai, model: {model_name}")

    def predict(
        self,
        question: str,
        choices: List[Dict],
        subject: str = "",
        context: str = "",
        retry_count: int = 2
    ) -> Dict:
        """
        Dự đoán đáp án cho 1 câu hỏi.

        Args:
            question: Nội dung câu hỏi
            choices: List [{"label": "A", "text": "..."}, ...]
            subject: Môn học (toán, lý, hóa, ...) - để tinh chỉnh prompt
            context: Context từ RAG (các câu tương tự)
            retry_count: Số lần thử lại nếu lỗi

        Returns:
            Dict: {
                "answer": "A/B/C/D",
                "confidence": 0.0-1.0,
                "explanation": "...",
                "reasoning": "...",
                "source": "llm",
                "tokens_used": 0,  # nếu có
                "model": self.model_name
            }
        """
        # Validate input
        if not question or not question.strip():
            return self._empty_result("Câu hỏi rỗng")

        valid_choices = [c for c in choices if c.get("text")]
        if len(valid_choices) < 2:
            return self._empty_result("Cần ít nhất 2 phương án")

        # Build prompt
        choices_text = self._format_choices(valid_choices)
        context_section = f"**Tham khảo từ câu hỏi tương tự:**\n{context}\n" if context else ""

        prompt = MRC_PROMPT_TEMPLATE.format(
            subject=subject or "trắc nghiệm",
            question=question.strip(),
            choices_text=choices_text,
            context_section=context_section
        )

        # Call LLM with retry + rate limit backoff
        for attempt in range(retry_count + 1):
            try:
                logger.debug(f"MRC attempt {attempt + 1}/{retry_count + 1}")

                if HAS_GENAI_NEW:
                    # New google.genai API
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_output_tokens
                        )
                    )
                    raw_text = response.text.strip() if response.text else ""
                else:
                    # Old google.generativeai API (deprecated)
                    response = self.model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_output_tokens,
                            candidate_count=1
                        )
                    )
                    raw_text = response.text.strip()

                # Parse JSON response
                result = self._parse_response(raw_text, valid_choices)

                # Validate answer
                if result["answer"] not in [c["label"].upper() for c in valid_choices]:
                    # Retry nếu answer invalid
                    if attempt < retry_count:
                        logger.warning(f"Answer invalid: {result['answer']}, retrying...")
                        continue
                    # Fallback: chọn câu đầu tiên có answer trong choices
                    result["answer"] = valid_choices[0]["label"].upper()
                    result["confidence"] = 0.3
                    result["explanation"] = "Không xác định được đáp án chắc chắn, chọn mặc định."

                result.update({
                    "source": "llm",
                    "model": self.model_name
                })

                # Log tokens if available
                if hasattr(response, 'usage_metadata'):
                    result["tokens_used"] = getattr(response.usage_metadata, 'total_token_count', 0)

                return result

            except Exception as e:
                err_str = str(e).lower()
                # Check for rate limit (429) - retry with backoff
                if "429" in str(e) and attempt < retry_count:
                    import time
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    logger.warning(f"Rate limit hit (429), waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

                logger.error(f"MRC error on attempt {attempt + 1}: {e}")
                if attempt >= retry_count:
                    return self._error_result(str(e))

        return self._error_result("Unknown error")

    def predict_batch(
        self,
        questions: List[Dict],
        subject: str = "",
        batch_size: int = 10
    ) -> List[Dict]:
        """
        Dự đoán hàng loạt (chạy sequential để tránh rate limit).

        Args:
            questions: List các dict {question, choices, ...}
            subject: Môn học chung
            batch_size: NOT USED - kept for compatibility

        Returns:
            List kết quả theo thứ tự
        """
        results = []
        for i, q in enumerate(questions, 1):
            logger.info(f"Đang xử lý câu {i}/{len(questions)}")
            result = self.predict(
                question=q.get("question", ""),
                choices=q.get("choices", []),
                subject=subject,
                context=""  # Không dùng RAG trong batch (đã xử lý trước)
            )
            result["question_id"] = q.get("id", i)
            result["question"] = q.get("question", "")
            results.append(result)

        return results

    def _format_choices(self, choices: List[Dict]) -> str:
        """Format choices thành string cho prompt."""
        lines = []
        for c in choices:
            label = (c.get("label") or "").upper().strip()
            text = (c.get("text") or "").strip()
            if label and text:
                lines.append(f"{label}. {text}")
        return "\n".join(lines)

    def _parse_response(self, raw_text: str, choices: List[Dict]) -> Dict:
        """
        Parse JSON response từ LLM.

        Args:
            raw_text: Text thô từ LLM
            choices: List choices để validate

        Returns:
            Dict với keys: answer, confidence, explanation, reasoning
        """
        # Default fallback
        default = {
            "answer": choices[0]["label"].upper() if choices else "",
            "confidence": 0.5,
            "explanation": "Không thể parse response",
            "reasoning": ""
        }

        if not raw_text:
            return default

        # Try to extract JSON block
        try:
            # Method 1: Find {...} block
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                answer = str(data.get("answer", "")).upper().strip()
                # Normalize answer (có thể có dạng "Đáp án: B" hoặc "B")
                answer = re.sub(r'[^A-D]', '', answer)  # Chỉ giữ A/B/C/D
                answer = answer[:1] if answer else ""

                return {
                    "answer": answer,
                    "confidence": float(data.get("confidence", 0.7)),
                    "explanation": str(data.get("explanation", "")).strip(),
                    "reasoning": str(data.get("reasoning", "")).strip()
                }

        except json.JSONDecodeError:
            pass

        # Method 2: Find answer letter directly
        try:
            # Tìm pattern như "answer": "B" hoặc "Đáp án: B"
            ans_match = re.search(r'"answer"\s*:\s*"([A-D])"', raw_text, re.IGNORECASE)
            if not ans_match:
                ans_match = re.search(r'Đáp\s*án\s*[:\-]?\s*([A-D])', raw_text, re.IGNORECASE)
            if not ans_match:
                ans_match = re.search(r'\b([A-D])\b', raw_text.upper())

            if ans_match:
                return {
                    "answer": ans_match.group(1).upper(),
                    "confidence": 0.6,
                    "explanation": raw_text[:300],
                    "reasoning": ""
                }
        except:
            pass

        return default

    def _empty_result(self, reason: str) -> Dict:
        """Trả về result rỗng khi input lỗi."""
        return {
            "answer": "",
            "confidence": 0.0,
            "explanation": reason,
            "reasoning": "",
            "source": "error",
            "error": True
        }

    def _error_result(self, error_msg: str) -> Dict:
        """Trả về result khi có lỗi."""
        return {
            "answer": "",
            "confidence": 0.0,
            "explanation": f"LLM error: {error_msg}",
            "reasoning": "",
            "source": "error",
            "error": True
        }

    def estimate_cost(
        self,
        prompt: str,
        estimated_output_tokens: int = 200
    ) -> float:
        """
        Ước tính chi phí cho 1 request (Gemini Flash).

        Args:
            prompt: Prompt string
            estimated_output_tokens: Số token output dự kiến

        Returns:
            float: Chi phí USD (theo Gemini Flash pricing)
        """
        # Gemini Flash pricing (tháng 4/2026):
        # Input: $0.000075 / 1K tokens  ($0.075 / 1M)
        # Output: $0.0003 / 1K tokens   ($0.30 / 1M)
        # Nếu có thay đổi, check: https://ai.google.dev/pricing

        # Đếm tokens thô (roughly: 1 token ~ 4 ký tự tiếng Anh)
        input_tokens = len(prompt) // 4

        input_cost = (input_tokens / 1000) * 0.000075
        output_cost = (estimated_output_tokens / 1000) * 0.0003

        return round(input_cost + output_cost, 6)

    def validate_answer_format(self, answer: str, choices: List[Dict]) -> bool:
        """Kiểm tra đáp án có hợp lệ không."""
        valid_labels = [c["label"].upper().strip() for c in choices]
        return answer.upper().strip() in valid_labels
