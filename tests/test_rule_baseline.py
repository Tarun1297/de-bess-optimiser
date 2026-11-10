"""Hand-checked days for the simple-rule baseline."""

import pandas as pd
import pytest

from rule_baseline import daily_profits, day_profit

# Fixed test battery, so a change to config/battery.yaml does not break these hand checks.
BATTERY = {
    "power_mw": 1.0,
    "energy_mwh": 2.0,
    "round_trip_efficiency": 0.88,
    "degradation_cost_eur_per_mwh": 0,
}


def test_hourly_day_by_hand():
    # Cheapest hours 10 and 20, most expensive 100 and 150, all others 50.
    prices = pd.Series([50.0] * 20 + [10, 20, 100, 150])
    # Buy 2 MWh: 10 + 20 = 30. Sell 2 x 0.88 = 1.76 MWh: 0.88 x (100 + 150) = 220.
    assert day_profit(prices, BATTERY, period_hours=1) == pytest.approx(190)


def test_quarter_hour_day_matches_the_same_hourly_day():
    # 8 quarter-hours at 10 and 8 at 100 hold the same energy as 2 hours at 10 and 2 at 100.
    quarter = pd.Series([50.0] * 80 + [10.0] * 8 + [100.0] * 8)
    hourly = pd.Series([50.0] * 20 + [10.0] * 2 + [100.0] * 2)
    assert day_profit(quarter, BATTERY, period_hours=0.25) == pytest.approx(156)
    assert day_profit(hourly, BATTERY, period_hours=1) == pytest.approx(156)


def test_flat_day_is_skipped():
    # 0.88 x 100 = 88 is less than the 100 paid, so the rule does not trade.
    assert day_profit(pd.Series([50.0] * 24), BATTERY, period_hours=1) == 0


def test_daily_profits_finds_each_day_and_its_period_length():
    # One hourly German day (15 June 2024) and one 15-minute day (15 October 2025), stored in UTC.
    hourly_start = pd.Timestamp("2024-06-15", tz="Europe/Berlin").tz_convert("UTC")
    quarter_start = pd.Timestamp("2025-10-15", tz="Europe/Berlin").tz_convert("UTC")
    prices = pd.DataFrame({
        "interval_start_utc": list(pd.date_range(hourly_start, periods=24, freq="h"))
        + list(pd.date_range(quarter_start, periods=96, freq="15min")),
        "price_eur_mwh": [50.0] * 20 + [10, 20, 100, 150] + [50.0] * 80 + [10.0] * 8 + [100.0] * 8,
    })
    daily = daily_profits(prices, BATTERY)
    assert len(daily) == 2
    assert list(daily.round(2)) == [190, 156]  # the same hand results as the tests above


def test_degradation_cost_lowers_profit():
    prices = pd.Series([50.0] * 20 + [10, 20, 100, 150])
    # 1.76 MWh sold x 10 EUR/MWh = 17.60 less than the 190 above.
    worn = {**BATTERY, "degradation_cost_eur_per_mwh": 10}
    assert day_profit(prices, worn, period_hours=1) == pytest.approx(172.4)
