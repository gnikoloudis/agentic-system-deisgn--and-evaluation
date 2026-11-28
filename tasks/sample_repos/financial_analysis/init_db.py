"""SQLite database setup script and test validator for Demo 1."""
import sqlite3
import json
from pathlib import Path

def setup_mock_financial_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS stock_prices")
    cur.execute("DROP TABLE IF EXISTS news_events")
    cur.execute("""
        CREATE TABLE stock_prices (
            ticker TEXT,
            trade_date TEXT,
            close_price REAL,
            daily_return REAL
        )
    """)
    cur.execute("""
        CREATE TABLE news_events (
            ticker TEXT,
            publish_date TEXT,
            headline TEXT,
            sentiment_score REAL
        )
    """)
    prices = [
        ("AAPL", "2024-01-10", 185.50, 0.015),
        ("AAPL", "2024-01-11", 182.10, -0.018),
        ("AAPL", "2024-01-12", 188.90, 0.037),
        ("NVDA", "2024-01-10", 540.00, 0.025),
        ("NVDA", "2024-01-11", 565.00, 0.046),
        ("NVDA", "2024-01-12", 590.00, 0.044),
    ]
    cur.executemany("INSERT INTO stock_prices VALUES (?, ?, ?, ?)", prices)
    news = [
        ("AAPL", "2024-01-10", "Apple announces new Vision Pro launch dates globally", 0.8),
        ("AAPL", "2024-01-11", "Barclays cuts iPhone supplier price target", -0.7),
        ("AAPL", "2024-01-12", "Record developer enthusiasm reported for VisionOS", 0.9),
        ("NVDA", "2024-01-10", "Nvidia reveals new generative AI enterprise chips at CES", 0.95),
        ("NVDA", "2024-01-11", "Analysts raise Nvidia quarterly targets by 20%", 0.85),
        ("NVDA", "2024-01-12", "Hyperscalers expand accelerator purchase commitments", 0.9),
    ]
    cur.executemany("INSERT INTO news_events VALUES (?, ?, ?, ?)", news)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_mock_financial_db(Path("financial_data.db"))
    print("financial_data.db created.")
