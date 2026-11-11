"""Linear programme: the most a battery can earn from one day of known prices."""

import pandas as pd
import pulp


def solve_day(prices: pd.Series, battery: dict, period_hours: float) -> tuple[float, pd.DataFrame]:
    """Best charge and discharge schedule for one day. Returns profit in EUR and the schedule."""
    T = range(len(prices))
    p = list(prices)
    h = period_hours
    prob = pulp.LpProblem("battery_day", pulp.LpMaximize)

    # Decisions per period, in MW. The bounds 0..power are the power limit.
    charge = [prob.add_variable(f"charge_{t}", 0, battery["power_mw"]) for t in T]
    discharge = [prob.add_variable(f"discharge_{t}", 0, battery["power_mw"]) for t in T]

    # State of charge in MWh at the end of each period. The bounds are the SoC range.
    e_min = battery["energy_mwh"] * battery["soc_min_pct"] / 100
    e_max = battery["energy_mwh"] * battery["soc_max_pct"] / 100
    soc = [prob.add_variable(f"soc_{t}", e_min, e_max) for t in T]

    # Goal: money from selling minus money spent on buying, minus wear per MWh sold.
    wear = battery["degradation_cost_eur_per_mwh"]
    prob += pulp.lpSum((p[t] - wear) * discharge[t] * h - p[t] * charge[t] * h for t in T)

    # Energy balance: stored now = stored before + bought x efficiency - sold.
    # The start level is a decision too, and the day must end where it started.
    eff = battery["round_trip_efficiency"]
    soc_start = prob.add_variable("soc_start", e_min, e_max)
    for t in T:
        before = soc[t - 1] if t > 0 else soc_start
        prob += soc[t] == before + charge[t] * h * eff - discharge[t] * h
    prob += soc[len(p) - 1] - soc_start == 0  # var == var compares objects in PuLP 4.2, so use a difference

    # Cycle limit: energy sold in the day at most max_cycles x battery size.
    prob += pulp.lpSum(discharge[t] * h for t in T) <= battery["max_cycles_per_day"] * battery["energy_mwh"]

    prob.solve(pulp.HiGHS(msg=False))
    schedule = pd.DataFrame({
        "price": p,
        "charge_mw": [v.value() for v in charge],
        "discharge_mw": [v.value() for v in discharge],
        "soc_mwh": [v.value() for v in soc],
    })
    return pulp.value(prob.objective), schedule


def daily_profits(prices: pd.DataFrame, battery: dict) -> pd.DataFrame:
    """LP profit and energy sold for every German day in `prices` (columns as in load_prices)."""
    day = prices.interval_start_utc.dt.tz_convert("Europe/Berlin").dt.date
    rows = []
    for d, g in prices.groupby(day):
        h = g.interval_start_utc.diff().median() / pd.Timedelta(hours=1)  # 1 or 0.25
        profit, s = solve_day(g.price_eur_mwh, battery, h)
        burn = ((s.charge_mw > 1e-6) & (s.discharge_mw > 1e-6)).sum()  # charge and discharge at once
        rows.append({"day": d, "profit_eur": profit, "sold_mwh": (s.discharge_mw * h).sum(), "burn_periods": burn})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from rule_baseline import load_battery

    battery = load_battery()
    lp = daily_profits(pd.read_parquet("data/prices_de_lu.parquet"), battery)
    lp.to_parquet("data/lp_daily.parquet", index=False)
    rule = pd.read_parquet("data/rule_daily.parquet")
    both = lp.merge(rule, on="day", suffixes=("_lp", "_rule"))
    year = pd.to_datetime(both.day).dt.year
    per_mw = both.groupby(year)[["profit_eur_lp", "profit_eur_rule"]].sum() / battery["power_mw"]
    per_mw["lp_vs_rule"] = per_mw.profit_eur_lp / per_mw.profit_eur_rule
    print(per_mw.round(2).to_string())
    print(f"days where the LP earns less than the rule: {(both.profit_eur_lp < both.profit_eur_rule - 1e-6).sum()}")
    print(f"average cycles per day: {lp.sold_mwh.mean() / battery['energy_mwh']:.2f}")
    print(f"periods with charge and discharge at once: {lp.burn_periods.sum()} on {(lp.burn_periods > 0).sum()} days")
