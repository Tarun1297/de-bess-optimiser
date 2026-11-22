"""Daily spreads, price level and volatility, and their descriptive statistics."""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import mannwhitneyu, spearmanr


def tb2(day_prices: pd.Series) -> float:
    """Average of the 2 most expensive hours minus the 2 cheapest (8 quarter-hours on 15-minute days)."""
    n = 2 if len(day_prices) <= 25 else 8
    p = np.sort(day_prices.to_numpy())
    return p[-n:].mean() - p[:n].mean()


def daily_table(prices: pd.DataFrame, lp_daily: pd.DataFrame) -> pd.DataFrame:
    """One row per German day: TB2 spread, average price, 30-day volatility, weekend flag, LP profit."""
    day = prices.interval_start_utc.dt.tz_convert("Europe/Berlin").dt.date
    g = prices.groupby(day).price_eur_mwh
    d = pd.DataFrame({"tb2": g.apply(tb2), "mean_price": g.mean()})
    d.index = pd.to_datetime(d.index)
    # Volatility of the market before this day: std of the previous 30 daily averages.
    # shift(1) leaves the day itself out, so the day's own prices never enter its volatility.
    d["vol30"] = d.mean_price.rolling(30).std().shift(1)
    d["weekend"] = d.index.day_of_week >= 5  # ponytail: public holidays count as weekdays; add a holiday list if they matter
    d["lp_profit"] = lp_daily.set_index(pd.to_datetime(lp_daily.day)).profit_eur
    return d


def describe(d: pd.DataFrame, by) -> pd.DataFrame:
    """Median, P10 and P90 of TB2 and LP profit per group."""
    q = d.groupby(by)[["tb2", "lp_profit"]].quantile([0.1, 0.5, 0.9]).unstack()
    q.columns = [f"{col}_p{int(p * 100)}" for col, p in q.columns]
    return q.round(1)


def weekday_vs_weekend(weekday: pd.Series, weekend: pd.Series) -> dict:
    """Mann-Whitney U, one-sided: are weekday values usually higher than weekend values?"""
    r = mannwhitneyu(weekday, weekend, alternative="greater")
    gaps = np.subtract.outer(weekday.to_numpy(), weekend.to_numpy())  # every weekday minus every weekend day
    return {
        "U": r.statistic,
        "p": r.pvalue,
        "weekday_win_share": r.statistic / gaps.size,
        "hodges_lehmann_gap": np.median(gaps),  # typical weekday-minus-weekend gap
        "median_weekday": weekday.median(),
        "median_weekend": weekend.median(),
    }


def weekend_effect_with_controls(d: pd.DataFrame, col: str) -> tuple[float, float]:
    """Weekend effect on `col` after removing month and year, with standard errors robust to autocorrelation."""
    x = d.assign(month=d.index.month, year=d.index.year, weekend=d.weekend.astype(int))
    fit = smf.ols(f"{col} ~ weekend + C(month) + C(year)", data=x).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    return fit.params["weekend"], fit.pvalues["weekend"]


def level_and_volatility(d: pd.DataFrame, col: str) -> dict:
    """Does `col` rise with the day's average price (level) and the previous 30 days' volatility (vol30)?

    Spearman for each alone, then one regression with both, without and with season controls.
    Level and vol30 are scaled to "1 standard deviation", so each effect is in EUR per typical change.
    """
    x = d.dropna(subset=["vol30"]).copy()
    out = {"sd_level": x.mean_price.std(), "sd_vol30": x.vol30.std()}
    for v in ("mean_price", "vol30"):
        out[f"spearman_{v}"] = tuple(spearmanr(x[col], x[v]))
    x["level"] = (x.mean_price - x.mean_price.mean()) / out["sd_level"]
    x["vol"] = (x.vol30 - x.vol30.mean()) / out["sd_vol30"]
    x["month"], x["year"], x["wkend"] = x.index.month, x.index.year, x.weekend.astype(int)
    for name, rhs in (("plain", "level + vol"), ("controls", "level + vol + wkend + C(month) + C(year)")):
        fit = smf.ols(f"{col} ~ {rhs}", data=x).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        out[name] = {k: (fit.params[k], fit.pvalues[k]) for k in ("level", "vol")}
    return out


def u_shape(d: pd.DataFrame, col: str) -> dict:
    """Is the link between price level and `col` a U-shape: wide at both low and high price levels?

    Adds level squared to the season-controlled regression. A positive, significant squared term means
    the line bends upward at both ends. Also returns the median of `col` in 10 equal-sized price-level groups.
    """
    x = d.dropna(subset=["vol30"]).copy()
    m, s = x.mean_price.mean(), x.mean_price.std()
    x["level"] = (x.mean_price - m) / s
    x["vol"] = (x.vol30 - x.vol30.mean()) / x.vol30.std()
    x["month"], x["year"], x["wkend"] = x.index.month, x.index.year, x.weekend.astype(int)
    fit = smf.ols(f"{col} ~ level + I(level**2) + vol + wkend + C(month) + C(year)", data=x).fit(
        cov_type="HAC", cov_kwds={"maxlags": 7})
    b1, b2 = fit.params["level"], fit.params["I(level ** 2)"]
    deciles = x.groupby(pd.qcut(x.mean_price, 10), observed=True)[col].median().round(1)
    return {
        "level": (b1, fit.pvalues["level"]),
        "level_squared": (b2, fit.pvalues["I(level ** 2)"]),
        "lowest_point_eur_mwh": m - b1 / (2 * b2) * s if b2 > 0 else None,  # price level where the U bottoms out
        "deciles": deciles,
    }


if __name__ == "__main__":
    d = daily_table(pd.read_parquet("data/prices_de_lu.parquet"), pd.read_parquet("data/lp_daily.parquet"))
    print(describe(d, d.index.year).to_string())
    print(describe(d, d.weekend.map({False: "weekday", True: "weekend"})).to_string())
    print(describe(d, d.index.month).to_string())
    for col in ("tb2", "lp_profit"):
        res = weekday_vs_weekend(d.loc[~d.weekend, col], d.loc[d.weekend, col])
        effect, p = weekend_effect_with_controls(d, col)
        print(f"\n{col}: " + ", ".join(f"{k} {v:.4g}" for k, v in res.items()))
        print(f"{col}: weekend effect after month and year {effect:.1f}, p {p:.4g}")
        print(f"{col}: level and volatility {level_and_volatility(d, col)}")
        u = u_shape(d, col)
        print(f"{col}: U-shape {({k: v for k, v in u.items() if k != 'deciles'})}")
        print(u["deciles"].to_string())
