"""Fetches recent RSS entries (last 24h) per category, skipping bad feeds."""
import re
from datetime import datetime, timedelta, timezone

import feedparser

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _entry_time(entry) -> datetime | None:
    # WHY: feedparser normalizes published/updated into struct_time when it can.
    struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not struct:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc)


def get_news(config: dict) -> dict:
    """Returns {category: [entries]} — entries from the last 24h only."""
    feeds_by_category = config.get("news_rss_feeds", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = {}

    for category, urls in feeds_by_category.items():
        entries = []
        for url in urls:
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries:
                    published = _entry_time(entry)
                    if published is None or published < cutoff:
                        continue  # WATCH: no date or stale — skip silently
                    entries.append({
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": _strip_html(entry.get("summary", "")),
                    })
            except Exception as e:
                # WHY: one malformed feed shouldn't take down the category.
                print(f"[news_collector] failed to fetch {url}: {e}")
                continue

        result[category] = entries  # empty list if all feeds skipped/stale

    return result
