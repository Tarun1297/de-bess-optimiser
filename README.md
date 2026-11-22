# de-bess-optimiser

How much could a battery earn in the German day-ahead market, and how much value does it add next to a solar plant?

## Projects

1. **Day-ahead arbitrage optimiser.** A 1 MW / 2 MWh battery trades DE-LU day-ahead prices from 2023 to 2026. A simple rule (charge in the cheapest hours, discharge in the most expensive) is the baseline. A linear programme (PuLP) finds the best schedule under power, state-of-charge, efficiency and cycle limits.
2. **Solar plant with a battery.** A 10 MW solar plant with a 5 MW / 10 MWh battery behind one grid connection, with and without grid charging.

## Method note

The model optimises against known day-ahead prices (perfect foresight), as industry benchmarks do. Real results are lower, because bids are placed before the auction clears and a large battery can move prices. Treat the result as an upper bound for day-ahead trading. Intraday trading is out of scope, because continuous intraday trade data is not freely available.

## Status

Work in progress.

- Done: DE-LU day-ahead prices from January 2023 to October 2026 (62,115 periods), stored in UTC. Prices are hourly until 30 September 2025 and every 15 minutes from 1 October 2025. Tests check for duplicates, missing prices and the period count of every day, including clock-change days (23 or 25 hours).
- Done: simple-rule baseline. Each day the battery charges in the cheapest periods that fill it (2 hours, or 8 quarter-hours) and sells the stored energy in the most expensive ones, and skips the day if the trade loses money.
- Done: linear-programme optimiser (PuLP with the HiGHS solver), one model per day. Rules: power limit, state of charge 5% to 95%, energy balance with 88% round-trip efficiency, at most 1.5 cycles per day, the day ends at the level it started, and a wear cost of €15 per MWh sold. Tests check every rule in the returned schedule and that the LP never earns less than the simple rule.
- Done: statistics of daily spreads and LP revenue (median, P10, P90 by year, month and weekday vs weekend), two hypothesis tests, and a day-ahead price forecast that the LP plans with and is then paid at actual prices.
- Next: a similar-day lag in the forecast (Monday uses Friday, Saturday uses last Saturday), chosen on a 2025 validation year in a separate change; then the solar plant project.

## Results so far

Revenue per MW, net of the €15/MWh wear cost, perfect foresight:

| Year | Simple rule | LP optimiser | LP vs rule |
| --- | --- | --- | --- |
| 2023 | €44,635 | €50,921 | +14% |
| 2024 | €54,177 | €61,306 | +13% |
| 2025 | €63,131 | €71,754 | +14% |
| 2026 (January to October) | €74,086 | €82,972 | +12% |

The LP earns at least as much as the rule on all 1,400 days and averages 1.24 cycles per day. Each extra €5/MWh of wear cost lowers the 2025 LP result by about €4,400 to €4,600 per MW (wear €0: €86,379; €30: €59,189).

### Statistics (daily values, 2023 to October 2026)

- **Weekend effect.** Weekend days earn less: −€33.5 per day after controlling for month and year (p = 0.00005). Mann-Whitney U on daily LP revenue: p = 0.0002.
- **U-shape.** Revenue is high on both cheap and expensive days and lowest near an average price of about €90/MWh. In a regression on 1,370 days (from 31 January 2023, after 30 days for the volatility input) with the squared price level, volatility, weekend, month and year, the squared term is €23.15 per day per step² (z = 5.22 with autocorrelation-robust HAC errors, p = 1.8e-7). Cheap days have midday prices near zero from solar; expensive days have high evening peaks. Both give wide spreads.

### Price forecast and forecast-based trading

The LP plans each day with a forecast, and the fixed plan is paid at the actual prices. Forecasts: the price of the same period one week earlier (naive), and a linear regression on yesterday's and last week's price, hour of day and weekday, trained on 2023–2025. Test: January to October 2026.

| Plan made with | MAE (€/MWh) | Revenue per MW | Share of perfect foresight |
| --- | --- | --- | --- |
| Actual prices (perfect foresight) | 0 | €82,972 | 100% |
| Regression forecast | 31.42 | €70,280 | 84.7% |
| Naive forecast | 42.65 | €66,006 | 79.6% |

The regression has a smaller error than the naive forecast (Diebold-Mariano test, p < 0.0001). A walk-forward test (refit every month, January 2024 to October 2026) gives a share of 76.3% in 2024, 81.1% in 2025 and 84.8% in 2026, and the regression beats the naive forecast in 28 of 34 months. The share rises over the years although the price error rises too: wider spreads make the order of cheap and expensive periods easier to get right, and that order is what the battery trades on.

## Set-up

```bash
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r pyproject.toml --extra dev
copy .env.example .env   # then add your ENTSO-E API key
python src/load_prices.py   # downloads prices to data/prices_de_lu.parquet
python src/rule_baseline.py # simple-rule revenue per month and year
python src/optimiser.py     # LP revenue per year, compared with the rule
python src/spread_stats.py  # descriptive statistics and hypothesis tests
python src/forecast.py      # price forecasts for 2026 and their errors
python src/forecast_lp.py   # plan with each forecast, paid at actual prices
python src/walk_forward.py  # the same with a monthly refit, 2024 to 2026
pytest
```

Battery assumptions are in `config/battery.yaml`. They are the author's assumptions, not data from a real asset. The wear cost of €15/MWh is an estimate for a lithium iron phosphate (LFP) battery; published figures range widely, so results for €0 to €30 are given above.
