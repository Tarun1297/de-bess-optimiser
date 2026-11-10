"""Download DE-LU day-ahead prices from ENTSO-E and save them as Parquet."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

AREA = "DE_LU"
OUT = Path("data/prices_de_lu.parquet")


def download_month(client: EntsoePandasClient, month_start: pd.Timestamp) -> pd.DataFrame:
    """One month of prices: one row per period, start time in UTC."""
    month_end = month_start + pd.offsets.MonthBegin(1)
    s = client.query_day_ahead_prices(AREA, start=month_start, end=month_end)
    s = s[s.index < month_end]  # entsoe-py also returns the period that starts at `end`
    return pd.DataFrame({
        "interval_start_utc": s.index.tz_convert("UTC"),
        "price_eur_mwh": s.to_numpy(),
    })


def download(start: str, end: str) -> pd.DataFrame:
    """All months from `start` up to, not including, `end`. Example: "2023-01", "2026-11"."""
    load_dotenv()
    client = EntsoePandasClient(api_key=os.environ["ENTSOE_API_KEY"])
    months = pd.date_range(start, end, freq="MS", tz="Europe/Berlin", inclusive="left")
    return pd.concat([download_month(client, m) for m in months], ignore_index=True)


if __name__ == "__main__":
    df = download("2023-01", "2026-11")  # January 2023 to October 2026, full months only
    OUT.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"{len(df)} rows saved to {OUT}")
