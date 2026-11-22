"""Checks that a forecast plan is paid at actual prices and that walk-forward never sees its test month."""

import numpy as np
import pandas as pd
import pytest

from forecast_lp import forecast_profits, settle
from optimiser import solve_day
from walk_forward import walk_forward

# Fixed here, as in test_optimiser, so a config change does not break the checks.
BATTERY = {
    "power_mw": 1.0, "energy_mwh": 2.0, "round_trip_efficiency": 0.88,
    "soc_min_pct": 5, "soc_max_pct": 95, "max_cycles_per_day": 1.5,
    "degradation_cost_eur_per_mwh": 15,
}


def test_settle_by_hand():
    # Buy 1 MWh at 10, sell 0.88 MWh at 100, wear 15 per MWh sold: 0.88 x 100 - 1 x 10 - 0.88 x 15 = 64.8.
    plan = pd.DataFrame({"charge_mw": [1.0, 0.0], "discharge_mw": [0.0, 0.88]})
    assert settle(plan, pd.Series([10.0, 100.0]), BATTERY, 1.0) == pytest.approx(64.8)


def test_plan_settled_at_its_own_prices_is_the_lp_profit():
    prices = pd.Series(np.random.default_rng(0).normal(80, 40, 96))
    profit, plan = solve_day(prices, BATTERY, 0.25)
    assert settle(plan, prices, BATTERY, 0.25) == pytest.approx(profit)


def _days(n, rng):
    # Whole German days: 2024-01-01 00:00 in Berlin is 23:00 UTC the day before.
    times = pd.date_range("2023-12-31 23:00", periods=n * 24, freq="h", tz="UTC")
    return pd.DataFrame({"interval_start_utc": times, "local": times.tz_convert("Europe/Berlin"),
                         "price_eur_mwh": rng.normal(80, 40, len(times))})


def test_perfect_forecast_earns_the_lp_profit_and_a_flat_one_earns_nothing():
    test = _days(3, np.random.default_rng(1))
    test["perfect"], test["flat"] = test.price_eur_mwh, 80.0
    lp = sum(solve_day(g.price_eur_mwh, BATTERY, 1.0)[0] for _, g in test.groupby(test.local.dt.date))
    assert forecast_profits(test, "perfect", BATTERY).profit_perfect.sum() == pytest.approx(lp)
    assert forecast_profits(test, "flat", BATTERY).profit_flat.abs().max() == pytest.approx(0, abs=1e-6)


def test_walk_forward_never_uses_later_months():
    # Change every price from March on: the forecasts for February must stay exactly the same.
    prices = _days(90, np.random.default_rng(2)).drop(columns="local")
    later = prices.copy()
    later.loc[later.interval_start_utc >= pd.Timestamp("2024-03-01", tz="Europe/Berlin"), "price_eur_mwh"] += 500
    feb = lambda df: df[df.local.dt.month == 2].regression.to_numpy()
    assert np.array_equal(feb(walk_forward(prices, "2024-02")), feb(walk_forward(later, "2024-02")))
