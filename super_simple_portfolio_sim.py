# file: super_simple_portfolio_sim.py
# Usage:
#   python super_simple_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv
#
# Intentionally simple:
# - No cycle detection (assumes valid input per prompt)
# - No delta math; recompute each portfolio every tick
# - Emit only when fully priceable AND value changed

from __future__ import annotations
import csv
import sys
from typing import Dict, List, Tuple, Optional

# Type aliases for clarity
Children = Dict[str, List[Tuple[str, float]]]


def read_portfolios_csv(path: str) -> Children:
    """
    Read portfolios.csv into:
      children[portfolio] = list of (child_name, shares)
    A portfolio starts where SHARES is blank; following rows with a number are members.
    Duplicate members under a portfolio are summed.
    """
    children: Children = {}
    current: Optional[str] = None

    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        if header != ["NAME", "SHARES"]:
            raise ValueError("portfolios.csv must start with: NAME,SHARES")

        for line_no, row in enumerate(r, start=2):
            if len(row) != 2:
                raise ValueError(f"Bad row at line {line_no}: {row}")
            name, shares = row[0].strip(), row[1].strip()

            if shares == "":  # portfolio header
                current = name
                children.setdefault(current, [])
            else:
                if current is None:
                    raise ValueError(f"Constituent before any portfolio header at line {line_no}")
                qty = float(shares)  # parse as double
                children[current].append((name, qty))

    # Aggregate duplicates
    for p, items in list(children.items()):
        agg: Dict[str, float] = {}
        for cname, qty in items:
            agg[cname] = agg.get(cname, 0.0) + qty
        children[p] = list(agg.items())
    return children


def compute_portfolio_value(
    portfolio: str,
    children: Children,
    seen_prices: Dict[str, float],
) -> Optional[float]:
    """
    Recursively compute the price of a portfolio from leaf stocks.
    Returns None if any required leaf price is missing.
    Assumes no cycles (per prompt’s "well-formed" input).
    """
    total = 0.0
    for child_name, weight in children[portfolio]:
        if child_name in children:
            # child is another portfolio -> recurse
            child_val = compute_portfolio_value(child_name, children, seen_prices)
            if child_val is None:
                return None
            total += weight * child_val
        else:
            # child is a leaf stock
            if child_name not in seen_prices:
                return None
            total += weight * seen_prices[child_name]
    return total


def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    children = read_portfolios_csv(portfolios_csv)
    portfolios = list(children.keys())  # in input order; any stable order is fine

    seen_prices: Dict[str, float] = {}
    last_value: Dict[str, float] = {}

    with open(prices_csv, newline="", encoding="utf-8") as fin, \
         open(output_csv, "w", newline="", encoding="utf-8") as fout:

        rin = csv.reader(fin)
        header = next(rin, None)
        if header != ["NAME", "PRICE"]:
            raise ValueError("prices.csv must start with: NAME,PRICE")

        wout = csv.writer(fout)
        wout.writerow(["NAME", "PRICE"])

        for line_no, row in enumerate(rin, start=2):
            if len(row) != 2:
                raise ValueError(f"Bad row at line {line_no}: {row}")
            name, price_str = row[0].strip(), row[1].strip()
            price = float(price_str)  # double

            # 1) Write the raw tick through
            wout.writerow([name, price])

            # 2) Update price cache
            seen_prices[name] = price

            # 3) Recompute every portfolio; emit only if fully known and changed
            for p in portfolios:
                val = compute_portfolio_value(p, children, seen_prices)
                if val is None:
                    continue  # still waiting on some leaf price(s)
                if (p not in last_value) or (val != last_value[p]):
                    wout.writerow([p, f"{val:.10g}"])
                last_value[p] = val


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python super_simple_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
