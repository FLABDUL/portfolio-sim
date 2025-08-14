# Portfolio Simulator

A Python program to calculate portfolio values from a stream of stock prices.

This project processes two CSV files:
- `portfolios.csv`: Defines portfolios as collections of stocks or other portfolios.
- `prices.csv`: A stream of stock price updates.

It outputs:
- `portfolio_prices.csv`: Contains all price updates **plus** portfolio values when computable.

---

## Problem Summary

Given:
- `portfolios.csv`: Defines portfolio structures.
- `prices.csv`: Time-ordered price updates.

Goal:
- Output `portfolio_prices.csv`, which includes price updates and portfolio values as they become available.

### Example:

```csv
# portfolios.csv
NAME,SHARES
TECH,
AAPL,100
MSFT,200
NVDA,300

# prices.csv
NAME,PRICE
AAPL,173
MSFT,425
NVDA,880

# portfolio_prices.csv
NAME,PRICE
AAPL,173.0
MSFT,425.0
NVDA,880.0
TECH,366300
```

---

## How to Run

```bash
python src/pandas_portfolio_sim.py data/portfolios.csv data/prices.csv data/portfolio_prices.csv
```

---

## File Formats

### portfolios.csv

```csv
NAME,SHARES
TECH,
AAPL,100
MSFT,200
NVDA,300
AUTOS,
FORD,100
TSLA,200
BMW,200
INDUSTRIALS,
TECH,2
AUTOS,3
```

### prices.csv

```csv
NAME,PRICE
AAPL,173
MSFT,425
NVDA,880
AAPL,174
FORD,12
TSLA,250
BMW,80
```

### portfolio_prices.csv

```csv
NAME,PRICE
AAPL,173.0
MSFT,425.0
NVDA,880.0
TECH,366300
AAPL,174.0
TECH,366400
FORD,12.0
TSLA,250.0
BMW,80.0
AUTOS,67200
INDUSTRIALS,934400
```

---

## Development & Tooling

### 🐍 Setup (recommended: virtual environment)

```bash
python -m venv .venv
# On PowerShell:
.venv\Scripts\Activate.ps1
# On bash:
source .venv/bin/activate
```

### 📦 Install Dependencies (with `uv`)

```bash
pip install uv
uv pip install -r requirements.txt
```

Or install directly:

```bash
uv pip install pandas pytest ruff tryceratops
```

---

## 🧪 Running Tests

```bash
pytest
```

---

## 🧼 Linting with Ruff

Check for issues:

```bash
ruff check .
```

Auto-fix issues:

```bash
ruff check . --fix
```

---

## ⚠️ Check Try/Except Blocks with Tryceratops

```bash
python -m tryceratops .
```

This highlights:
- Unhandled or overly broad exceptions
- Logging issues in `except` blocks
- Bad patterns like bare `except:`

---

## 📄 Requirements

You can regenerate your `requirements.txt` anytime with:

```bash
uv pip freeze > requirements.txt
```

---