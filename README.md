# Portfolio Simulator

A Python program to calculate portfolio values from a stream of stock prices.

This project demonstrates several implementations of the same problem, progressing from the simplest possible approach to more advanced and efficient techniques. You can choose the implementation that matches your current learning level, and discuss possible improvements in interviews.

---

## Problem Summary

Given:
- `portfolios.csv`: Defines portfolios as collections of stocks or other portfolios.
- `prices.csv`: A stream of stock price updates.

Goal:
- Output `portfolio_prices.csv`, which contains the original price updates **plus** calculated portfolio prices as soon as enough information is available.

Example from the brief:
```
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

## Implementations

### 1. **Ultra Minimal** (`ultra_min_portfolio_sim.py`)
- Reads `portfolios.csv` into a dictionary of portfolio → constituents.
- Reads `prices.csv` line-by-line.
- **Recomputes every portfolio from scratch** for each new price.
- Only emits a portfolio price when:
  - All required stock prices are known.
  - Its value changed since last emission.

**Pros:**
- Very short, easy to read.
- Perfect for explaining the problem without distractions.

**Cons:**
- Inefficient for large inputs (recomputes everything every time).
- No cycle detection (assumes valid input).

**Interview expansion ideas:**
- Add cycle detection.
- Pre-flatten portfolios into leaf stocks once, then compute with simple sums.
- Introduce reverse dependencies (stock → affected portfolios).

---

### 2. **Super Simple with Reverse Dependencies**
- Builds a reverse dependency graph: stock → [portfolios affected].
- On each price update:
  - Recomputes only affected portfolios, not all portfolios.
- Keeps memoized flattened weights for each portfolio.

**Pros:**
- Faster for large streams (avoids recomputing unrelated portfolios).
- Still understandable for intermediate developers.

**Cons:**
- Slightly more complex logic.

**Interview expansion ideas:**
- Implement delta updates: only adjust portfolio prices by (Δprice × weight) instead of full recompute.

---

### 3. **Pandas Version** (`pandas_portfolio_sim.py`)
- Uses Pandas DataFrames for:
  - Efficient CSV reading/writing.
  - Vectorized portfolio price calculations.
- Suitable when datasets fit in memory and you want cleaner data handling.

**Pros:**
- Concise code with Pandas’ built-in features.
- Easy to join, group, and aggregate.

**Cons:**
- More memory use.
- Less control over per-tick streaming unless chunked reading is used.

**Interview expansion ideas:**
- Compare Pandas vs. Polars vs. Numba with benchmarks (e.g., Hyperfine).
- Discuss trade-offs between readability and performance.

---

### 4. **High Performance Version**
- Uses:
  - **Polars** for faster CSV streaming.
  - **Numba** for JIT-compiling core computation loops.
  - Integer ID mapping for portfolios/stocks instead of strings.
- Minimizes Python overhead.

**Pros:**
- Scales to millions of price ticks and thousands of portfolios.
- Demonstrates strong optimization knowledge.

**Cons:**
- Higher complexity, less beginner-friendly.

**Interview expansion ideas:**
- Memory layout optimization (contiguous arrays).
- Multithreading or multiprocessing for independent portfolios.

---

## How to Run

Example:
```bash
python ultra_min_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv
```

---

## File Formats

### portfolios.csv
```
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
```
NAME,PRICE
AAPL,173
MSFT,425
NVDA,880
AAPL,174
FORD,12
TSLA,250
BMW,80
```

### portfolio_prices.csv (output from ultra minimal)
```
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

## Learning Path

You can start with the **Ultra Minimal** version, then add improvements step-by-step:
1. Add cycle detection.
2. Add reverse dependencies.
3. Add delta updates.
4. Replace data structures with more efficient ones.
5. Move to Pandas/Polars for large dataset handling.
6. Use Numba to compile computation loops.

By showing this progression in an interview, you demonstrate both problem-solving and scalability thinking.
