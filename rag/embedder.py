"""Fetches YouTube transcripts, chunks them, and feeds them into a VectorStore."""
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


def get_transcript(video_id: str, languages: list[str] = ["en", "hi"]) -> str | None:
    """Returns the joined transcript text, or None if unavailable.

    Tries languages in order (default: English, then Hindi).
    """
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
        return " ".join(snippet.text for snippet in fetched)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        # WHY: these are the expected "no transcript" cases — not a crash condition.
        print(f"[embedder] transcript unavailable for {video_id}: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Sliding-window character chunking (simple, no tokenizer dependency)."""
    if not text:
        return []

    chunks = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += step
    return chunks


def process_video_transcript(video_id: str, vector_store) -> bool:
    """Orchestrates fetch -> chunk -> store. Returns False (logged) on any failure."""
    transcript = get_transcript(video_id)
    if transcript is None:
        return False  # already logged in get_transcript

    chunks = chunk_text(transcript)
    if not chunks:
        print(f"[embedder] no chunks produced for {video_id} (empty transcript)")
        return False

    vector_store.add_documents(video_id, chunks)
    return True