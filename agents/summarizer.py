"""Summarizes video transcripts (via RAG chunks) and news items using Gemini,
with a local Ollama fallback if Gemini is unavailable."""
import os
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
    # WHY: constructing genai.Client() validates the API key immediately —
    # doing this at import time would crash the whole module (and everything
    # that imports it) if GEMINI_API_KEY is unset. Lazy init lets that failure
    # be caught per-call instead, matching this project's error-handling style.
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _generate_with_retry(prompt: str):
    try:
        return _get_client().models.generate_content(model="gemini-2.5-flash", contents=prompt)
    except APIError as e:
        if e.code in (429, 503):
            print(f"[summarizer] got {e.code}, waiting 15s before retry...")
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
        # WHY: any Gemini failure (quota, network, auth) falls through to Ollama
        # rather than killing the caller — matches project-wide "never crash" style.
        print(f"[fallback] Gemini failed, trying Ollama... ({e})")
        try:
            resp = requests.post(
                _OLLAMA_URL,
                json={"model": _OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except Exception as e2:
            # WATCH: this fires if Ollama isn't running (`ollama serve`) or
            # qwen3:4b isn't pulled — both are prerequisites, not bugs here.
            print(f"[fallback] Ollama also failed: {e2}")
            return None

_VIDEO_SYSTEM_PROMPT = (
    "You are a geopolitical/business analyst. Summarize this video transcript "
    "in English in 3-4 crisp sentences, regardless of the transcript's "
    "original language. Focus on the key claims, events, or insights — not filler."
)


def summarize_video(video: dict, vector_store) -> dict:
    """Summarizes a video's transcript chunks via call_llm. Never raises."""
    base = {"title": video["title"], "channel": video["channel_name"]}

    chunks = vector_store.query(video["video_id"], video["title"], n_results=5)
    if not chunks:
        return {**base, "summary": None, "status": "no_transcript"}

    try:
        transcript_text = "\n".join(chunks)
        summary = call_llm(transcript_text, _VIDEO_SYSTEM_PROMPT)
        if summary is None:
            return {**base, "summary": None, "status": "error", "error": "Gemini and Ollama both failed"}
        return {**base, "summary": summary, "status": "ok"}
    except Exception as e:
        # WHY: one bad call must not crash the whole batch of summaries.
        print(f"[summarizer] failed to summarize video {video.get('video_id')}: {e}")
        return {**base, "summary": None, "status": "error", "error": str(e)}


def summarize_news_item(item: dict, category: str) -> dict:
    """Passes through short/clear RSS summaries; only calls the LLM if too thin."""
    summary = item.get("summary", "") or ""

    if len(summary.split()) >= 20:
        # WHY: don't waste API calls rewriting an already-adequate blurb.
        final_summary = summary
    else:
        result = call_llm(
            item.get("title", ""),
            "Summarize this news item title in 1-2 crisp sentences, in English, focused on the key fact.",
        )
        final_summary = result if result is not None else summary  # WATCH: fall back to whatever we had, even if thin

    return {
        "title": item.get("title", ""),
        "link": item.get("link", ""),
        "summary": final_summary,
        "category": category,
    }
