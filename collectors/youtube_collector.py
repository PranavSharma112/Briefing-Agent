"""Fetches recent (last 24h) videos per configured channel via YouTube Data API."""
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()


def get_recent_videos(config: dict) -> list[dict]:
    """Returns a flat list of recent video dicts across all configured channels.

    Raises ValueError immediately if YOUTUBE_API_KEY is missing — fail fast
    at the top rather than deep inside an API call.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is missing or empty — set it in .env")

    youtube = build("youtube", "v3", developerKey=api_key)
    published_after = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    videos = []
    for channel in config.get("youtube_channels", []):
        name = channel.get("name", "")
        channel_id = channel.get("channel_id", "")

        if not channel_id:
            print(f"[youtube_collector] skipping '{name}': no channel_id set")
            continue

        try:
            response = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                order="date",
                publishedAfter=published_after,
                type="video",
                maxResults=5,
            ).execute()

            for item in response.get("items", []):
                snippet = item["snippet"]
                videos.append({
                    "video_id": item["id"]["videoId"],
                    "title": snippet["title"],
                    "channel_name": name,
                    "published_at": snippet["publishedAt"],
                    "thumbnail_url": snippet["thumbnails"]["default"]["url"],
                })
        except Exception as e:
            # WHY: one failed channel (quota, bad ID, network) must not stop others.
            print(f"[youtube_collector] failed to fetch channel '{name}': {e}")
            continue

    return videos
