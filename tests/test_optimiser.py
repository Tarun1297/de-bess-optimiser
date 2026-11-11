"""Checks that the LP respects every battery rule and never earns less than the simple rule."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from optimiser import solve_day
from rule_baseline import day_profit

# Same numbers as config/battery.yaml, fixed here so a config change does not break the checks.
BATTERY = {
    "power_mw": 1.0, "energy_mwh": 2.0, "round_trip_efficiency": 0.88,
    "soc_min_pct": 5, "soc_max_pct": 95, "max_cycles_per_day": 1.5,
    "degradation_cost_eur_per_mwh": 0,
}
TOY = {
    "power_mw": 1, "energy_mwh": 1, "round_trip_efficiency": 0.9,
    "soc_min_pct": 0, "soc_max_pct": 100, "max_cycles_per_day": 2,
    "degradation_cost_eur_per_mwh": 0,
}
TOL = 1e-6


def random_days():
    """Twenty made-up days, hourly and 15-minute, some with negative prices."""
    rng = np.random.default_rng(42)
    days = []
    for i in range(20):
        n, h = (24, 1.0) if i % 2 else (96, 0.25)
        days.append((pd.Series(rng.normal(70, 60, n)), h))
    return days


def test_toy_day_by_hand():
    # Start 0.1, buy 1 at 20, sell 1 at 80, buy 1 at 10 and 0.111 at 30, sell 1 at 120,
    # buy 0.111 at 60 to end at 0.1: 80 + 120 - 20 - 10 - 3.33 - 6.67 = 160.
    profit, _ = solve_day(pd.Series([20.0, 80, 10, 30, 120, 60]), TOY, period_hours=1)
    assert profit == pytest.approx(160.0)


@pytest.mark.parametrize("prices, h", random_days())
def test_every_rule_holds(prices, h):
    _, s = solve_day(prices, BATTERY, h)
    eff, e = BATTERY["round_trip_efficiency"], BATTERY["energy_mwh"]
    # Power limit
    assert s.charge_mw.between(-TOL, BATTERY["power_mw"] + TOL).all()
    assert s.discharge_mw.between(-TOL, BATTERY["power_mw"] + TOL).all()
    # State-of-charge range: 5% to 95% of 2 MWh
    assert s.soc_mwh.between(0.05 * e - TOL, 0.95 * e + TOL).all()
    # Energy balance, period by period
    change = (s.charge_mw * eff - s.discharge_mw) * h
    assert np.allclose(s.soc_mwh.diff().iloc[1:], change.iloc[1:], atol=TOL)
    # Same start and end: the level before period 1 equals the level after the last period
    start = s.soc_mwh.iloc[0] - change.iloc[0]
    assert start == pytest.approx(s.soc_mwh.iloc[-1], abs=TOL)
    # Cycle limit: at most 1.5 x 2 MWh sold
    assert (s.discharge_mw * h).sum() <= BATTERY["max_cycles_per_day"] * e + TOL


@pytest.mark.parametrize("prices, h", random_days())
def test_lp_never_earns_less_than_the_rule(prices, h):
    profit, _ = solve_day(prices, BATTERY, h)
    assert profit >= day_profit(prices, BATTERY, h) - TOL


def test_degradation_cost_means_less_trading():
    prices, h = random_days()[0]
    free, s_free = solve_day(prices, BATTERY, h)
    worn, s_worn = solve_day(prices, {**BATTERY, "degradation_cost_eur_per_mwh": 30}, h)
    assert worn < free
    assert s_worn.discharge_mw.sum() <= s_free.discharge_mw.sum() + TOL


PRICES = Path("data/prices_de_lu.parquet")


@pytest.mark.skipif(not PRICES.exists(), reason="run src/load_prices.py first")
def test_lp_beats_the_rule_on_real_days():
    df = pd.read_parquet(PRICES)
    df["day"] = df.interval_start_utc.dt.tz_convert("Europe/Berlin").dt.date
    days = list(df.groupby("day"))
    sample = days[::50]  # every 50th day: hourly and 15-minute, all seasons
    for _, g in sample:
        h = g.interval_start_utc.diff().median() / pd.Timedelta(hours=1)
        lp, _ = solve_day(g.price_eur_mwh, BATTERY, h)
        assert lp >= day_profit(g.price_eur_mwh, BATTERY, h) - TOL
