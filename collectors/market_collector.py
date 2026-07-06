"""Fetches last close + % change for configured tickers via yfinance."""
import yfinance as yf


def get_market_summary(config: dict) -> list[dict]:
    """Returns a list of {ticker, last_close, pct_change} dicts.

    Each ticker is fetched independently — one bad ticker/network hiccup
    is skipped, not fatal to the rest.
    """
    tickers = config.get("markets", {}).get("tickers", [])
    results = []

    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) < 2:
                # WATCH: need at least 2 closes to compute % change.
                print(f"[market_collector] insufficient data for {ticker}")
                continue

            last_close = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2]
            pct_change = (last_close - prev_close) / prev_close * 100

            results.append({
                "ticker": ticker,
                "last_close": round(float(last_close), 2),
                "pct_change": round(float(pct_change), 2),
            })
        except Exception as e:
            # WHY: yfinance raises varied exception types (network, parsing);
            # broad catch here is intentional to keep the pipeline alive.
            print(f"[market_collector] failed to fetch {ticker}: {e}")
            continue

    return results
