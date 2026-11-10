"""Data checks on the saved DE-LU day-ahead prices."""

from pathlib import Path

import pandas as pd
import pytest

PRICES = Path("data/prices_de_lu.parquet")
SWITCH = pd.Timestamp("2025-10-01", tz="Europe/Berlin")  # first day with 15-minute prices

pytestmark = pytest.mark.skipif(not PRICES.exists(), reason="run src/load_prices.py first")


@pytest.fixture(scope="module")
def local_counts():
    """Number of price periods per German calendar day."""
    df = pd.read_parquet(PRICES)
    local = df.interval_start_utc.dt.tz_convert("Europe/Berlin")
    return local.dt.normalize().value_counts().sort_index()


def test_stored_in_utc():
    df = pd.read_parquet(PRICES)
    assert str(df.interval_start_utc.dt.tz) == "UTC"


def test_no_duplicates_or_missing_prices():
    df = pd.read_parquet(PRICES)
    assert not df.interval_start_utc.duplicated().any()
    assert not df.price_eur_mwh.isna().any()


def test_every_day_has_the_right_number_of_periods(local_counts):
    days = pd.date_range(local_counts.index[0], local_counts.index[-1], freq="D")
    hours = pd.Series([(d + pd.DateOffset(days=1) - d) / pd.Timedelta(hours=1) for d in days], index=days)
    expected = hours.where(days < SWITCH, hours * 4)  # 4 quarter-hours per hour after the switch
    actual = local_counts.reindex(days, fill_value=0)
    wrong = actual[actual != expected]
    assert wrong.empty, f"days with wrong period count:\n{wrong.head()}"


@pytest.mark.parametrize("day, periods", [
    ("2023-03-26", 23),   # spring clock change, hourly
    ("2023-10-29", 25),   # autumn clock change, hourly
    ("2025-10-26", 100),  # autumn clock change, 15-minute
    ("2026-03-29", 92),   # spring clock change, 15-minute
])
def test_clock_change_days(local_counts, day, periods):
    assert local_counts[pd.Timestamp(day, tz="Europe/Berlin")] == periods
