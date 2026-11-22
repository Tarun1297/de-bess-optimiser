"""Day-ahead price forecasts: same time last week (baseline) and a linear regression."""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm
from sklearn.linear_model import LinearRegression

TEST_START = pd.Timestamp("2026-01-01", tz="Europe/Berlin")  # train on 2023-2025, test on 2026


def add_lags(prices: pd.DataFrame) -> pd.DataFrame:
    """Add the price 24 hours and 7 days earlier.

    Both are known when bids close (12:00 the day before), because those auctions are already done.
    merge_asof takes the latest price at or before that time, so a 15-minute period
    can use an hourly price from before 1 October 2025.
    """
    # ponytail: lags are in UTC, so on the 2 clock-change days a year they are one hour off German clock time
    df = prices.sort_values("interval_start_utc").reset_index(drop=True)
    ref = df[["interval_start_utc", "price_eur_mwh"]].rename(columns={"interval_start_utc": "key", "price_eur_mwh": "lag"})
    for days in (1, 7):
        key = pd.DataFrame({"key": df.interval_start_utc - pd.Timedelta(days=days)})
        df[f"lag{days}"] = pd.merge_asof(key, ref, on="key").lag.to_numpy()
    df["local"] = df.interval_start_utc.dt.tz_convert("Europe/Berlin")
    return df.dropna(subset=["lag7"])


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Yesterday's and last week's price, plus one 0/1 column per hour of day and per weekday.

    drop_first leaves out hour 0 and Monday: they are the reference that the other columns are compared to.
    With every column kept, the weights would not be unique, so they could not be read.
    """
    hour = pd.get_dummies(df.local.dt.hour, prefix="h", dtype=float, drop_first=True)
    weekday = pd.get_dummies(df.local.dt.day_of_week, prefix="wd", dtype=float, drop_first=True)
    return pd.concat([df[["lag1", "lag7"]], hour, weekday], axis=1)


def forecasts(prices: pd.DataFrame) -> pd.DataFrame:
    """Test-period rows with the actual price, the baseline (lag7) and the regression forecast."""
    df = add_lags(prices)
    X = features(df)
    train = df.local < TEST_START
    model = LinearRegression().fit(X[train], df.price_eur_mwh[train])
    test = df[~train].copy()
    test["naive"] = test.lag7
    test["regression"] = model.predict(X[~train])
    return test


def errors(test: pd.DataFrame) -> pd.DataFrame:
    """MAE and RMSE in EUR/MWh for each forecast."""
    rows = {}
    for col in ("naive", "regression"):
        e = test[col] - test.price_eur_mwh
        rows[col] = {"MAE": e.abs().mean(), "RMSE": np.sqrt((e**2).mean())}
    return pd.DataFrame(rows).T.round(2)


def diebold_mariano(loss_a: pd.Series, loss_b: pd.Series, maxlags: int = 7) -> dict:
    """Is forecast B more accurate than forecast A? One value per day for each loss.

    d = loss of A minus loss of B. H0: the average d is 0 (equally accurate).
    H1: the average d is above 0 (B is more accurate). The standard error is HAC,
    so it allows for days with similar errors in a row.
    """
    d = pd.DataFrame({"d": (loss_a - loss_b).to_numpy()})
    fit = smf.ols("d ~ 1", data=d).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    stat = fit.tvalues["Intercept"]
    return {"mean_d": fit.params["Intercept"], "DM": stat, "p_one_sided": norm.sf(stat), "days": len(d)}


def daily_losses(test: pd.DataFrame) -> pd.DataFrame:
    """Average absolute and squared error per German day, for each forecast."""
    day = test.local.dt.date
    out = {}
    for col in ("naive", "regression"):
        e = test[col] - test.price_eur_mwh
        out[f"abs_{col}"] = e.abs().groupby(day).mean()
        out[f"sq_{col}"] = (e**2).groupby(day).mean()
    return pd.DataFrame(out)


if __name__ == "__main__":
    test = forecasts(pd.read_parquet("data/prices_de_lu.parquet"))
    test.to_parquet("data/forecast_2026.parquet", index=False)
    print(f"test periods: {len(test)}, from {test.local.min()} to {test.local.max()}")
    print(errors(test).to_string())
    loss = daily_losses(test)
    for kind in ("abs", "sq"):
        print(kind, diebold_mariano(loss[f"{kind}_naive"], loss[f"{kind}_regression"]))
