# Portfolio Simulator

A Python program to calculate portfolio values from a stream of stock prices.

---

## 📂 Overview

This tool processes:

- ✅ `portfolios.csv`: Defines portfolios as collections of stocks or other portfolios.
- ✅ `prices.csv`: A time-ordered stream of stock price updates.

It outputs:

- 📤 `portfolio_prices.csv`: All price updates, plus computed portfolio values as soon as enough prices are known.

---

## 🚀 How to Run

```bash
python src/pandas_portfolio_sim.py data/portfolios.csv data/prices.csv data/portfolio_prices.csv
```

Make sure the `data/` directory contains the `portfolios.csv` and `prices.csv` input files.

---

## 💡 Example

### Input: `portfolios.csv`
```csv
NAME,SHARES
TECH,
AAPL,100
MSFT,200
NVDA,300
```

### Input: `prices.csv`
```csv
NAME,PRICE
AAPL,173
MSFT,425
NVDA,880
```

### Output: `portfolio_prices.csv`
```csv
NAME,PRICE
AAPL,173.0
MSFT,425.0
NVDA,880.0
TECH,366300
```

---

## ⚙️ Environment Setup

### 1. Create a Virtual Environment (recommended)

```bash
python -m venv .venv
# Activate it:
# PowerShell
.venv\Scripts\Activate.ps1
# or Bash
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install uv
uv pip install -r requirements.txt
```

---

## 🧪 Optional: Developer & Testing Instructions

### Run All Tests

```bash
pytest
```

### Run Linting with Ruff

```bash
ruff check .
```

To auto-fix:

```bash
ruff check . --fix
```

---

## 📦 Regenerate Dependencies

```bash
uv pip freeze > requirements.txt
```

---