# de-bess-optimiser

How much could a battery earn in the German day-ahead market, and how much value does it add next to a solar plant?

## Projects

1. **Day-ahead arbitrage optimiser.** A 1 MW / 2 MWh battery trades DE-LU day-ahead prices from 2023 to 2026. A simple rule (charge in the cheapest hours, discharge in the most expensive) is the baseline. A linear programme (PuLP) finds the best schedule under power, state-of-charge, efficiency and cycle limits.
2. **Solar plant with a battery.** A 10 MW solar plant with a 5 MW / 10 MWh battery behind one grid connection, with and without grid charging.

## Method note

The model optimises against known day-ahead prices (perfect foresight), as industry benchmarks do. Real results are lower, because bids are placed before the auction clears and a large battery can move prices. Treat the result as an upper bound for day-ahead trading. Intraday trading is out of scope, because continuous intraday trade data is not freely available.

## Status

Work in progress. Set-up is done. Next: load and validate 15-minute prices.

## Set-up

```bash
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r pyproject.toml --extra dev
copy .env.example .env   # then add your ENTSO-E API key
pytest
```

Battery assumptions are in `config/battery.yaml`. They are the author's assumptions, not data from a real asset.
