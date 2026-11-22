"""Hand checks for the daily spread table."""

import numpy as np
import pandas as pd
import pytest

from spread_stats import (
    daily_table,
    level_and_volatility,
    tb2,
    u_shape,
    weekday_vs_weekend,
)


def test_tb2_hourly_and_quarter_hourly():
    # Hourly: top 2 = 100, 150 (avg 125); bottom 2 = 10, 20 (avg 15); TB2 = 110.
    assert tb2(pd.Series([50.0] * 20 + [10, 20, 100, 150])) == pytest.approx(110)
    # 15-minute: 8 periods at 10 and 8 at 100, so TB2 = 90.
    assert tb2(pd.Series([50.0] * 80 + [10.0] * 8 + [100.0] * 8)) == pytest.approx(90)


def test_mann_whitney_toy_example_by_hand():
    # Weekdays 90, 110, 300 win 8 of 9 matches; 2 of 20 label splits reach U >= 8; median gap 50.
    r = weekday_vs_weekend(pd.Series([90.0, 110, 300]), pd.Series([40.0, 70, 100]))
    assert r["U"] == 8
    assert r["p"] == pytest.approx(0.10)
    assert r["hodges_lehmann_gap"] == pytest.approx(50)


def test_level_effect_is_found_when_it_exists():
    # Made-up days where the spread rises by 0.5 EUR for every EUR of price level, and volatility does nothing.
    rng = np.random.default_rng(0)
    days = pd.date_range("2024-01-01", periods=730)
    level = rng.normal(80, 30, len(days))
    d = pd.DataFrame({"mean_price": level, "tb2": 0.5 * level + rng.normal(0, 10, len(days)),
                      "vol30": rng.normal(20, 5, len(days)), "weekend": days.day_of_week >= 5}, index=days)
    r = level_and_volatility(d, "tb2")
    effect, p = r["controls"]["level"]
    assert effect == pytest.approx(0.5 * r["sd_level"], rel=0.1)  # 0.5 EUR per EUR, times 1 standard deviation
    assert p < 0.001
    assert r["controls"]["vol"][1] > 0.01  # no volatility effect built in, so no strong evidence for one


def test_u_shape_is_found_with_its_lowest_point():
    # Made-up days where the spread is lowest at a price level of 80 and rises on both sides.
    rng = np.random.default_rng(1)
    days = pd.date_range("2024-01-01", periods=730)
    level = rng.normal(80, 40, len(days))
    d = pd.DataFrame({"mean_price": level, "tb2": 50 + 0.02 * (level - 80) ** 2 + rng.normal(0, 10, len(days)),
                      "vol30": rng.normal(20, 5, len(days)), "weekend": days.day_of_week >= 5}, index=days)
    r = u_shape(d, "tb2")
    assert r["level_squared"][0] > 0 and r["level_squared"][1] < 0.001
    assert r["lowest_point_eur_mwh"] == pytest.approx(80, abs=5)


def test_vol30_uses_only_earlier_days():
    # 40 hourly days with daily averages 1, 2, ..., 40.
    start = pd.Timestamp("2024-01-01", tz="Europe/Berlin").tz_convert("UTC")
    times = pd.date_range(start, periods=40 * 24, freq="h")
    prices = pd.DataFrame({"interval_start_utc": times, "price_eur_mwh": [float(i // 24 + 1) for i in range(40 * 24)]})
    lp = pd.DataFrame({"day": pd.date_range("2024-01-01", periods=40).date, "profit_eur": 0.0})
    d = daily_table(prices, lp)
    assert d.vol30.iloc[:30].isna().all()  # fewer than 30 earlier days: no value
    # Day 31 sees days 1 to 30 (averages 1..30), not its own average 31.
    assert d.vol30.iloc[30] == pytest.approx(pd.Series(range(1, 31), dtype=float).std())
