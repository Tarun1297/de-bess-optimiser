"""Simple-rule baseline: charge in the cheapest periods of a day, sell in the most expensive."""

import pandas as pd
import yaml


def load_battery(path: str = "config/battery.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def day_profit(prices: pd.Series, battery: dict, period_hours: float) -> float:
    """Profit in EUR for one day. `prices` in EUR/MWh, one value per period of `period_hours`.

    Charge at full power in the n cheapest periods, where n periods fill the battery
    (2 hours = 2 periods hourly or 8 periods at 15 minutes). Sell the stored energy,
    after round-trip losses, spread over the n most expensive periods.
    Skip the day (profit 0) if the trade loses money.
    """
    n = round(battery["energy_mwh"] / battery["power_mw"] / period_hours)
    bought_per_period = battery["power_mw"] * period_hours  # MWh
    eff = battery["round_trip_efficiency"]
    p = prices.sort_values().to_numpy()
    cost = p[:n].sum() * bought_per_period
    revenue = p[-n:].sum() * bought_per_period * eff
    degradation = n * bought_per_period * eff * battery["degradation_cost_eur_per_mwh"]
    return max(revenue - cost - degradation, 0.0)


def daily_profits(prices: pd.DataFrame, battery: dict) -> pd.Series:
    """Rule profit in EUR for every German day in `prices` (columns as in load_prices)."""
    day = prices.interval_start_utc.dt.tz_convert("Europe/Berlin").dt.date
    result = {}
    for d, g in prices.groupby(day):
        period_hours = g.interval_start_utc.diff().median() / pd.Timedelta(hours=1)  # 1 or 0.25
        result[d] = day_profit(g.price_eur_mwh, battery, period_hours)
    return pd.Series(result, name="profit_eur")


if __name__ == "__main__":
    battery = load_battery()
    daily = daily_profits(pd.read_parquet("data/prices_de_lu.parquet"), battery)
    month = pd.to_datetime(daily.index).to_period("M")
    monthly = daily.groupby(month).sum() / battery["power_mw"]  # EUR per MW
    print(monthly.round(0).to_string())
    print(monthly.groupby(monthly.index.year).sum().round(0).to_string())
    print(f"days traded: {(daily > 0).sum()} of {len(daily)}")
