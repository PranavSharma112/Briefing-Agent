"""Fetches today's weather from Open-Meteo (free, no API key)."""
import requests

# WHY: Open-Meteo returns integer WMO codes, not text — map the common ones.
# WATCH: uncovered codes fall back to "Unknown" rather than raising.
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

API_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather(config: dict) -> dict | None:
    """Returns {temp, condition, forecast} for today, or None on failure."""
    try:
        lat = config["weather"]["lat"]
        lon = config["weather"]["lon"]

        resp = requests.get(
            API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                "timezone": "auto",
                "forecast_days": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data["current"]
        daily = data["daily"]

        return {
            "temp": current["temperature_2m"],
            "condition": _WMO_CODES.get(current["weather_code"], "Unknown"),
            "forecast": {
                "high": daily["temperature_2m_max"][0],
                "low": daily["temperature_2m_min"][0],
                "condition": _WMO_CODES.get(daily["weather_code"][0], "Unknown"),
            },
        }
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        # WATCH: never let one failed source crash the whole pipeline.
        print(f"[weather_collector] failed to fetch weather: {e}")
        return None
