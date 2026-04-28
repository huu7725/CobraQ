"""
MRC Service - Machine Reading Comprehension.
Sử dụng LLM (Groq - Llama) để đọc câu hỏi trắc nghiệm và chọn đáp án đúng.
"""

import json
import re
import logging
import os
import time
from typing import Dict, List, Optional

import requests

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
    Sử dụng Groq API (Llama) để đọc và hiểu câu hỏi trắc nghiệm.
    """

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_output_tokens: int = 1024
    ):
        """
        Khởi tạo MRCService với Groq API.

        Args:
            api_key: Groq API key
            model_name: Tên model Groq (llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768)
            temperature: Độ ngẫu nhiên (0.0-1.0). Thấp hơn = chắc chắn hơn
            max_output_tokens: Giới hạn output tokens
        """
        if not api_key:
            raise ValueError("Groq API key is required")

        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        logger.info(f"MRCService initialized with Groq, model: {model_name}")

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
                "tokens_used": 0,
                "model": self.model_name
            }
        """
        if not question or not question.strip():
            return self._empty_result("Câu hỏi rỗng")

        valid_choices = [c for c in choices if c.get("text")]
        if len(valid_choices) < 2:
            return self._empty_result("Cần ít nhất 2 phương án")

        choices_text = self._format_choices(valid_choices)
        context_section = f"**Tham khảo từ câu hỏi tương tự:**\n{context}\n" if context else ""

        prompt = MRC_PROMPT_TEMPLATE.format(
            subject=subject or "trắc nghiệm",
            question=question.strip(),
            choices_text=choices_text,
            context_section=context_section
        )

        for attempt in range(retry_count + 1):
            try:
                logger.debug(f"MRC attempt {attempt + 1}/{retry_count + 1}")

                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "Bạn là chuyên gia giải đề thi trắc nghiệm. Trả lời CHÍNH XÁC theo định dạng JSON được yêu cầu."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "max_completion_tokens": self.max_output_tokens
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                response = requests.post(
                    self.GROQ_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                if response.status_code == 429:
                    if attempt < retry_count:
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Rate limit (429), waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return self._error_result("Rate limit exceeded")

                if response.status_code != 200:
                    return self._error_result(f"Groq API error: {response.status_code} - {response.text[:200]}")

                data = response.json()
                raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens_used = data.get("usage", {}).get("total_tokens", 0)

                result = self._parse_response(raw_text.strip() if raw_text else "", valid_choices)

                if result["answer"] not in [c["label"].upper() for c in valid_choices]:
                    if attempt < retry_count:
                        logger.warning(f"Answer invalid: {result['answer']}, retrying...")
                        continue
                    result["answer"] = valid_choices[0]["label"].upper()
                    result["confidence"] = 0.3
                    result["explanation"] = "Không xác định được đáp án chắc chắn, chọn mặc định."

                result.update({
                    "source": "llm",
                    "model": self.model_name,
                    "tokens_used": tokens_used
                })

                return result

            except requests.exceptions.Timeout:
                logger.error(f"MRC timeout on attempt {attempt + 1}")
                if attempt >= retry_count:
                    return self._error_result("Request timeout")
            except Exception as e:
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
        """
        results = []
        for i, q in enumerate(questions, 1):
            logger.info(f"Đang xử lý câu {i}/{len(questions)}")
            result = self.predict(
                question=q.get("question", ""),
                choices=q.get("choices", []),
                subject=subject,
                context=""
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
        """
        default = {
            "answer": choices[0]["label"].upper() if choices else "",
            "confidence": 0.5,
            "explanation": "Không thể parse response",
            "reasoning": ""
        }

        if not raw_text:
            return default

        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                answer = str(data.get("answer", "")).upper().strip()
                answer = re.sub(r'[^A-D]', '', answer)
                answer = answer[:1] if answer else ""

                return {
                    "answer": answer,
                    "confidence": float(data.get("confidence", 0.7)),
                    "explanation": str(data.get("explanation", "")).strip(),
                    "reasoning": str(data.get("reasoning", "")).strip()
                }
        except json.JSONDecodeError:
            pass

        try:
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
        Ước tính chi phí cho 1 request (Groq Llama 3.3 70B).

        Groq pricing (llama-3.3-70b-versatile):
        - Input: $0.00 / 1M tokens (miễn phí!)
        - Output: $0.00 / 1M tokens (miễn phí!)

        Check latest: https://console.groq.com/docs/models
        """
        return 0.0

    def validate_answer_format(self, answer: str, choices: List[Dict]) -> bool:
        """Kiểm tra đáp án có hợp lệ không."""
        valid_labels = [c["label"].upper().strip() for c in choices]
        return answer.upper().strip() in valid_labels
