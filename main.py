"""Orchestrates the full daily briefing pipeline, end to end."""
import time
from datetime import date
from pathlib import Path

import yaml

from collectors.weather_collector import get_weather
from collectors.market_collector import get_market_summary
from collectors.news_collector import get_news
from collectors.youtube_collector import get_recent_videos
from rag.vector_store import VectorStore
from rag.embedder import process_video_transcript
from agents.summarizer import summarize_video
from agents.quote_agent import get_daily_quote
from agents.synthesizer import synthesize_brief
from mailer import render_email, send_email

with open("config.yaml") as f:
    config = yaml.safe_load(f)

LAST_RUN_FILE = Path(".last_run.txt")


def main():
    today = date.today().isoformat()

    if LAST_RUN_FILE.exists():
        last_run = LAST_RUN_FILE.read_text().strip()
        if last_run == today:
            print("Already sent today's briefing, skipping")
            return

    print("Fetching weather...")
    weather = get_weather(config)

    print("Fetching markets...")
    markets = get_market_summary(config)

    print("Fetching news...")
    news = get_news(config)

    print("Fetching videos...")
    videos = get_recent_videos(config)
    print(f"  Found {len(videos)} videos in the last 24h.")

    vector_store = VectorStore()

    video_summaries = []
    total = len(videos)
    for i, video in enumerate(videos, start=1):
        print(f"Summarizing video {i}/{total}: {video['title']}...")
        process_video_transcript(video["video_id"], vector_store)
        try:
            summary = summarize_video(video, vector_store)
        except Exception as e:
            print(f"[main] failed to summarize {video['title']}: {e}")
            summary = {
                "title": video["title"],
                "channel": video["channel_name"],
                "summary": "Summary unavailable",
                "status": "error",
            }
        video_summaries.append(summary)
        time.sleep(4)  # WHY: stay under Gemini free-tier 5 req/min limit

    print("Fetching daily quote...")
    time.sleep(4)  # WHY: same rate-limit spacing before the next Gemini call
    quote = get_daily_quote()

    print("Synthesizing brief...")
    brief = synthesize_brief(video_summaries, news, markets, weather, quote)

    print("Rendering email...")
    html = render_email(brief)

    print("Sending email...")
    sent = send_email(html, config, date=brief["date"])

    if sent:
        LAST_RUN_FILE.write_text(today)
        print("Done — briefing sent successfully.")
    else:
        # WHY: email failure shouldn't hide that everything upstream worked.
        print("Email failed to send, but the brief was fully assembled:")
        print(f"  - {len(video_summaries)} video summaries")
        print(f"  - {len(brief['ai_news'])} AI news items, {len(brief['local_news'])} local news items")
        print(f"  - {len(markets)} market tickers")


if __name__ == "__main__":
    main()
