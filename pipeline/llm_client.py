"""LLM client wrappers and routing."""

from __future__ import annotations

import time
from typing import Literal

import google.generativeai as genai
from groq import Groq

from config import load_settings


class LLMClient:
    """Unified LLM client with provider-specific wrappers and retries."""

    def __init__(self) -> None:
        settings = load_settings()
        self._groq = Groq(api_key=settings.groq_api_key)
        genai.configure(api_key=settings.gemini_api_key)
        self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")

    def call_groq(self, prompt: str, retries: int = 3, timeout_s: float = 30.0) -> str:
        """Call Groq for Q&A generation with retries."""
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._groq.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    timeout=timeout_s,
                )
                return (response.choices[0].message.content or "").strip()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Groq call failed after {retries} attempts: {last_error}") from last_error

    def call_gemini(self, prompt: str, retries: int = 3) -> str:
        """Call Gemini for summarization with retries."""
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._gemini_model.generate_content(prompt)
                return (response.text or "").strip()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Gemini call failed after {retries} attempts: {last_error}") from last_error

    def call_llm(self, prompt: str, task_type: Literal["qa", "summarization"]) -> str:
        """Route prompt to Groq (qa) or Gemini (summarization)."""
        if task_type == "qa":
            return self.call_groq(prompt)
        if task_type == "summarization":
            return self.call_gemini(prompt)
        raise ValueError(f"Unsupported task_type: {task_type}")
