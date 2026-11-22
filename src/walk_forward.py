"""Walk-forward test: refit the regression every month on all earlier data, then run the forecast LP."""

import pandas as pd
from sklearn.linear_model import LinearRegression

from forecast import add_lags, features
from forecast_lp import forecast_profits

FIRST_TEST = "2024-01"  # at least one full year (all seasons) to train on


def walk_forward(prices: pd.DataFrame, first_test: str = FIRST_TEST) -> pd.DataFrame:
    """Rows from first_test on, with naive and regression forecasts made only from earlier months."""
    df = add_lags(prices)
    X = features(df)
    month = df.local.dt.tz_localize(None).dt.to_period("M")
    out = []
    for m in month[month >= pd.Period(first_test)].unique():
        train, test = month < m, month == m  # expanding window: everything before this month
        model = LinearRegression().fit(X[train], df.price_eur_mwh[train])
        rows = df[test].copy()
        rows["naive"] = rows.lag7
        rows["regression"] = model.predict(X[test])
        out.append(rows)
    return pd.concat(out)


if __name__ == "__main__":
    from rule_baseline import load_battery

    battery = load_battery()
    test = walk_forward(pd.read_parquet("data/prices_de_lu.parquet"))
    perfect = pd.read_parquet("data/lp_daily.parquet")[["day", "profit_eur"]]
    out = perfect[perfect.day.isin(set(test.local.dt.date))]
    for col in ("naive", "regression"):
        out = out.merge(forecast_profits(test, col, battery), on="day")
    out.to_parquet("data/walk_forward_daily.parquet", index=False)
    cols = ["profit_eur", "profit_naive", "profit_regression"]
    by_month = out.groupby(pd.to_datetime(out.day).dt.to_period("M"))[cols].sum()
    share = by_month[cols[1:]].div(by_month.profit_eur, axis=0)
    by_year = out.groupby(pd.to_datetime(out.day).dt.year)[cols].sum()
    print("share per year:\n", by_year[cols[1:]].div(by_year.profit_eur, axis=0).round(3).to_string())
    print("share per month (min, median, max):\n", share.describe().loc[["min", "50%", "max"]].round(3).to_string())
    print("months where regression beats naive:", (share.profit_regression > share.profit_naive).sum(), "of", len(share))
