"""Plan with a price forecast, settle at the actual prices, compare with perfect foresight."""

import pandas as pd

from optimiser import solve_day


def settle(schedule: pd.DataFrame, actual: pd.Series, battery: dict, h: float) -> float:
    """Money the planned schedule really earns at the actual prices, minus wear."""
    p = actual.to_numpy()
    net_mwh = (schedule.discharge_mw - schedule.charge_mw).to_numpy() * h
    wear = battery["degradation_cost_eur_per_mwh"] * (schedule.discharge_mw.to_numpy() * h).sum()
    return float((p * net_mwh).sum() - wear)


def forecast_profits(test: pd.DataFrame, col: str, battery: dict) -> pd.DataFrame:
    """For each German day: plan on forecast column `col`, then settle at the actual price."""
    rows = []
    for d, g in test.groupby(test.local.dt.date):
        h = g.interval_start_utc.diff().median() / pd.Timedelta(hours=1)  # 0.25 in 2026
        _, plan = solve_day(g[col], battery, h)  # the LP only sees the forecast
        rows.append({"day": d, f"profit_{col}": settle(plan, g.price_eur_mwh, battery, h)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from rule_baseline import load_battery

    battery = load_battery()
    test = pd.read_parquet("data/forecast_2026.parquet")
    perfect = pd.read_parquet("data/lp_daily.parquet")[["day", "profit_eur"]]
    out = perfect[perfect.day.isin(set(test.local.dt.date))]
    for col in ("naive", "regression"):
        out = out.merge(forecast_profits(test, col, battery), on="day")
    out.to_parquet("data/forecast_lp_2026.parquet", index=False)
    total = out.drop(columns="day").sum()
    print(total.round(0).to_string())
    print("share of perfect foresight:", (total / total.profit_eur).round(3).drop("profit_eur").to_dict())
