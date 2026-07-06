"""Assembles all collected/summarized data into one structured briefing dict.

Pure data assembly — no Claude calls here, keeps this trivially testable.
"""
from datetime import date

_GEOPOLITICS_CHANNELS = ("chanakya", "career 247", "career247")
_BUSINESS_CHANNELS = ("think school", "rahul malodia")


def _matches(channel_name: str, keywords: tuple[str, ...]) -> bool:
    name = (channel_name or "").lower()
    return any(keyword in name for keyword in keywords)


def synthesize_brief(
    video_summaries: list[dict],
    news: dict,
    market_data: list[dict],
    weather: dict | None,
    quote: dict,
) -> dict:
    """Combines all inputs into the final dict shape for the HTML template."""
    video_summaries = video_summaries or []
    news = news or {}
    market_data = market_data or []

    geopolitics = [v for v in video_summaries if _matches(v.get("channel"), _GEOPOLITICS_CHANNELS)]
    business = [v for v in video_summaries if _matches(v.get("channel"), _BUSINESS_CHANNELS)]

    today = date.today()
    formatted_date = f"{today.strftime('%A, %B')} {today.day}, {today.year}"

    return {
        "date": formatted_date,
        "quote": quote,
        "weather": weather if weather is not None else "Weather unavailable",
        "markets": market_data,
        "geopolitics": geopolitics,
        "business": business,
        "ai_news": news.get("ai_news", []),
        "local_news": news.get("local_news", []),
    }
