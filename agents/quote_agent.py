"""Fetches a daily Stoic/notable-figure quote via Gemini, with a safe fallback."""
import json
import os
import re
import time

import requests
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()

_client = None

_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = "qwen3:4b"


def _get_client():
    # WHY: see agents/summarizer.py — eager client construction crashes the
    # module on import if GEMINI_API_KEY is missing. Lazy init defers that
    # failure into the try/except below.
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _generate_with_retry(prompt: str):
    # WHY: same rate-limit story as summarizer.py — one retry after 15s
    # cooldown on 429/503 before giving up.
    try:
        return _get_client().models.generate_content(model="gemini-2.0-flash", contents=prompt)
    except APIError as e:
        if e.code in (429, 503):
            print(f"[quote_agent] got {e.code}, waiting 15s before retry...")
            time.sleep(15)
            return _get_client().models.generate_content(model="gemini-2.0-flash", contents=prompt)
        raise


def call_llm(prompt: str, system: str = "") -> str | None:
    """Tries Gemini (with retry), falls back to local Ollama, returns None if both fail."""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    try:
        response = _generate_with_retry(full_prompt)
        return response.text
    except Exception as e:
        print(f"[fallback] Gemini failed, trying Ollama... ({e})")
        try:
            resp = requests.post(
                _OLLAMA_URL,
                json={"model": _OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except Exception as e2:
            # WATCH: fires if Ollama isn't running (`ollama serve`) or
            # qwen3:4b isn't pulled — prerequisites, not bugs here.
            print(f"[fallback] Ollama also failed: {e2}")
            return None

_SYSTEM_PROMPT = 'Return ONLY valid JSON: {"quote": "...", "author": "..."}. No markdown fences, no extra text.'

_FALLBACK = {
    "quote": "You have power over your mind, not outside events.",
    "author": "Marcus Aurelius",
}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def get_daily_quote() -> dict:
    """Returns {"quote", "author"}. Falls back to a hardcoded quote on any failure."""
    try:
        prompt = (
            "Give one Stoic or notable historical figure's quote "
            "(Marcus Aurelius, Seneca, Epictetus, or a historical "
            "leader/thinker) relevant to resilience, strategy, or "
            "clarity of thought."
        )
        raw = call_llm(prompt, _SYSTEM_PROMPT)
        if raw is None:
            return _FALLBACK
        cleaned = _FENCE_RE.sub("", raw).strip()  # WATCH: model sometimes wraps in ```json fences anyway
        parsed = json.loads(cleaned)
        if "quote" in parsed and "author" in parsed:
            return {"quote": parsed["quote"], "author": parsed["author"]}
        return _FALLBACK
    except Exception as e:
        # WHY: this step must never break the pipeline — always have a quote.
        print(f"[quote_agent] failed to get daily quote: {e}")
        return _FALLBACK
