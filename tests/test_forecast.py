"""Checks that the forecast inputs only look back in time."""

import pandas as pd
import pytest

from forecast import add_lags, diebold_mariano


def test_lags_are_the_prices_one_day_and_one_week_earlier():
    # 20 hourly days in winter (no clock change); the price is the hour number, so each lag is easy to check.
    start = pd.Timestamp("2024-01-01", tz="UTC")
    times = pd.date_range(start, periods=20 * 24, freq="h")
    df = add_lags(pd.DataFrame({"interval_start_utc": times, "price_eur_mwh": range(len(times))}))
    assert df.price_eur_mwh.iloc[0] == 7 * 24  # the first 7 days have no lag7 and are dropped
    assert (df.price_eur_mwh - df.lag1 == 24).all()
    assert (df.price_eur_mwh - df.lag7 == 7 * 24).all()


def test_diebold_mariano_by_hand():
    # Daily errors of A: 50, 40, 60, 30, 45. Of B: 35, 38, 40, 32, 30. Differences d: 15, 2, 20, -2, 15.
    # Mean 10. With maxlags=0 the HAC standard error is the plain one with n in the denominator:
    # sqrt(sum((d - 10)^2) / 5) / sqrt(5) = sqrt(358 / 5) / sqrt(5) = 3.784, so DM = 10 / 3.784 = 2.643.
    r = diebold_mariano(pd.Series([50.0, 40, 60, 30, 45]), pd.Series([35.0, 38, 40, 32, 30]), maxlags=0)
    assert r["mean_d"] == pytest.approx(10)
    assert r["DM"] == pytest.approx(10 / (358 / 5) ** 0.5 * 5**0.5, rel=1e-6)


def test_quarter_hour_can_use_last_weeks_hourly_price():
    # Hourly prices for a week, then quarter-hours: 10:15 uses last week's 10:00 price.
    hourly = pd.date_range("2025-09-24", periods=7 * 24, freq="h", tz="UTC")
    quarter = pd.date_range("2025-10-01", periods=96, freq="15min", tz="UTC")
    prices = pd.DataFrame({"interval_start_utc": hourly.append(quarter),
                           "price_eur_mwh": [float(t.hour) for t in hourly] + [0.0] * 96})
    df = add_lags(prices).set_index("interval_start_utc")
    assert df.loc[pd.Timestamp("2025-10-01 10:15", tz="UTC"), "lag7"] == 10.0
