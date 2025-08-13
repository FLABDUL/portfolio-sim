# file: ultra_min_portfolio_sim.py
# Usage: python ultra_min_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv
#
# Intentionally simple:
# - No cycle detection (assumes valid input as per brief)
# - No dependency indexing; recompute each portfolio every tick
# - Emit a portfolio only when fully known AND its value changed

import csv
import sys
from typing import Dict, List, Tuple, Optional

Children = Dict[str, List[Tuple[str, float]]]


def read_portfolios_csv(path: str) -> Children:
    """Parse portfolios.csv into children[portfolio] = [(child_name, shares_float), ...]."""
    children: Children = {}
    current: Optional[str] = None

    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        if header != ["NAME", "SHARES"]:
            raise ValueError("portfolios.csv must start with header: NAME,SHARES")
        for row in r:
            if len(row) != 2:
                continue  # tolerate blank lines
            name, shares = row[0].strip(), (row[1] or "").strip()
            if shares == "":  # portfolio header
                current = name
                children.setdefault(current, [])
            else:
                if current is None:
                    raise ValueError("Constituent before any portfolio header.")
                children[current].append((name, float(shares)))  # parse as double

    # Aggregate duplicates per portfolio (AAPL listed twice -> sum)
    for p, items in list(children.items()):
        agg: Dict[str, float] = {}
        for cname, qty in items:
            agg[cname] = agg.get(cname, 0.0) + qty
        children[p] = list(agg.items())
    return children


def price_portfolio(p: str, children: Children, seen: Dict[str, float]) -> Optional[float]:
    """Recursively compute portfolio price; return None until all leaf prices are known."""
    total = 0.0
    for child, w in children[p]:
        if child in children:  # child is another portfolio
            val = price_portfolio(child, children, seen)
            if val is None:
                return None
            total += w * val
        else:  # child is a leaf stock
            if child not in seen:
                return None
            total += w * seen[child]
    return total


def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    children = read_portfolios_csv(portfolios_csv)
    portfolios = list(children.keys())  # stable iteration order is fine
    seen: Dict[str, float] = {}
    last_value: Dict[str, float] = {}

    with open(prices_csv, newline="", encoding="utf-8") as fin, \
         open(output_csv, "w", newline="", encoding="utf-8") as fout:

        rin = csv.reader(fin)
        header = next(rin, None)
        if header != ["NAME", "PRICE"]:
            raise ValueError("prices.csv must start with header: NAME,PRICE")

        wout = csv.writer(fout)
        wout.writerow(["NAME", "PRICE"])

        for row in rin:
            if len(row) != 2:
                continue  # tolerate blank lines
            name, price_str = row[0].strip(), row[1].strip()
            price = float(price_str)  # parse as double

            # 1) Echo the input tick
            wout.writerow([name, price])

            # 2) Update price cache
            seen[name] = price

            # 3) Recompute every portfolio; emit only if fully known AND changed
            for p in portfolios:
                val = price_portfolio(p, children, seen)
                if val is None:
                    continue
                if p not in last_value or val != last_value[p]:
                    wout.writerow([p, f"{val:.10g}"])
                last_value[p] = val


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python ultra_min_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
