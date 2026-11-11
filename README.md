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
- Next: statistics of daily spreads, a hypothesis test, and a price forecast.

## Results so far

Revenue per MW, net of the €15/MWh wear cost, perfect foresight:

| Year | Simple rule | LP optimiser | LP vs rule |
| --- | --- | --- | --- |
| 2023 | €44,635 | €50,921 | +14% |
| 2024 | €54,177 | €61,306 | +13% |
| 2025 | €63,131 | €71,754 | +14% |
| 2026 (January to October) | €74,086 | €82,972 | +12% |

The LP earns at least as much as the rule on all 1,400 days and averages 1.24 cycles per day. Each extra €5/MWh of wear cost lowers the 2025 LP result by about €4,400 to €4,600 per MW (wear €0: €86,379; €30: €59,189).

## Set-up

```bash
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r pyproject.toml --extra dev
copy .env.example .env   # then add your ENTSO-E API key
python src/load_prices.py   # downloads prices to data/prices_de_lu.parquet
python src/rule_baseline.py # simple-rule revenue per month and year
python src/optimiser.py     # LP revenue per year, compared with the rule
pytest
```

Battery assumptions are in `config/battery.yaml`. They are the author's assumptions, not data from a real asset. The wear cost of €15/MWh is an estimate for a lithium iron phosphate (LFP) battery; published figures range widely, so results for €0 to €30 are given above.
