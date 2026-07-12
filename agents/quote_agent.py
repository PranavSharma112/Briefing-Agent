"""Fetches a daily notable-figure quote via Gemini, with an expanded 366-quote local pool fallback."""
import json
import os
import random
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()

_client = None

_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = "qwen3:4b"

# ROBUST PATH RESOLUTION: Computes exact absolute path to agents/quotes_db.json
DB_PATH = Path(__file__).parent / "quotes_db.json"


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _generate_with_retry(prompt: str):
    try:
        return _get_client().models.generate_content(model="gemini-2.5-flash", contents=prompt)
    except APIError as e:
        if e.code in (429, 503):
            print(f"[quote_agent] got {e.code}, waiting 15s before retry...")
            time.sleep(15)
            return _get_client().models.generate_content(model="gemini-2.5-flash", contents=prompt)
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
            print(f"[fallback] Ollama also failed: {e2}")
            return None


_SYSTEM_PROMPT = 'Return ONLY valid JSON: {"quote": "...", "author": "...", "category": "..."}. No markdown fences, no extra text.'


def load_fallback_pool() -> list:
    """Loads the hardcoded 366 quotes pool from the local JSON database file."""
    try:
        if DB_PATH.exists():
            return json.loads(DB_PATH.read_text(encoding="utf-8"))
        else:
            print(f"[quote_agent] Database file missing at expected path: {DB_PATH.resolve()}")
    except Exception as e:
        print(f"[quote_agent] Error reading quotes database file: {e}")
    
    return [{"quote": "You have power over your mind - not outside events.", "author": "Marcus Aurelius", "category": "Stoicism"}]


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def get_daily_quote() -> dict:
    """Returns {"quote", "author", "category"}. Falls back to a randomly chosen quote from the 366 pool."""
    fallback_pool = load_fallback_pool()
    
    try:
        # User preference-mapped LLM prompt
        prompt = (
            "Provide one profound, simple quote that conveys incredible depth, increases maturity/wisdom, "
            "and inspires passion or creativity. "
            "The quote must come from an open, diverse group of global icons including: "
            "1. Stoics/Philosophers (Marcus Aurelius, Seneca, Epictetus, Socrates, Confucius)\n"
            "2. Spiritual Masters & Strategists (Sadhguru, Sun Tzu, Chanakya)\n"
            "3. Pioneers & Inventors (Steve Jobs, Edison, Tesla, Dr. APJ Abdul Kalam)\n"
            "4. Elite Sports Legends across all history and sports (Michael Jordan, Muhammad Ali, Kobe Bryant, Pelé, Serena Williams, etc.)\n"
            "5. Successful Emperors and historical tactical visionaries.\n"
            "Return JSON matching the schema format cleanly, mapping the matched category."
        )
        
        raw = call_llm(prompt, _SYSTEM_PROMPT)
        if raw is None:
            return random.choice(fallback_pool)
            
        cleaned = _FENCE_RE.sub("", raw).strip()
        parsed = json.loads(cleaned)
        
        if "quote" in parsed and "author" in parsed:
            return {
                "quote": parsed["quote"],
                "author": parsed["author"],
                "category": parsed.get("category", "General Wisdom")
            }
        return random.choice(fallback_pool)
        
    except Exception as e:
        print(f"[quote_agent] failed to get daily quote: {e}")
        return random.choice(fallback_pool)