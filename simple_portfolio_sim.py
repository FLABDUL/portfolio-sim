# file: simple_portfolio_sim.py
# Usage:
#   python simple_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv
#
# Pure Python, no pandas. Clear & correct, easy to extend.

from __future__ import annotations
import csv
import sys
from typing import Dict, List, Tuple


def read_portfolios_csv(path: str) -> Dict[str, List[Tuple[str, float]]]:
    """
    Parse portfolios.csv into:
      children[portfolio] = list of (child_name, shares_as_float)
    A portfolio header is a row with blank SHARES.
    """
    children: Dict[str, List[Tuple[str, float]]] = {}
    current: str | None = None

    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        if header is None or header != ["NAME", "SHARES"]:
            raise ValueError("portfolios.csv must start with header: NAME,SHARES")

        for i, (name, shares) in enumerate(r, start=2):
            name = name.strip()
            if shares is None:
                shares = ""
            shares = shares.strip()

            if shares == "":  # portfolio header
                current = name
                if current not in children:
                    children[current] = []
            else:
                if current is None:
                    raise ValueError(f"Constituent before any portfolio header at line {i}")
                qty = float(shares)  # parse as double
                children[current].append((name, qty))

    # Aggregate duplicates (AAPL listed twice -> sum)
    for p, items in list(children.items()):
        agg: Dict[str, float] = {}
        for cname, qty in items:
            agg[cname] = agg.get(cname, 0.0) + qty
        children[p] = list(agg.items())
    return children


def expand_flattened(children: Dict[str, List[Tuple[str, float]]]) -> Dict[str, Dict[str, float]]:
    """
    Iteratively expand portfolios into leaf stock weights with no recursion/memoization.
    Algorithm:
      - portfolios = set of defined portfolio names
      - leaf stock = any child name not in portfolios
      - Repeatedly look for a portfolio whose children are all either leaf stocks
        or portfolios already expanded; compute its flat composition and add it.
      - If a full pass adds nothing and some portfolios remain -> cycle.
    Returns:
      flattened[portfolio] = {stock: weight_per_1_portfolio}
    """
    portfolios = set(children.keys())
    flattened: Dict[str, Dict[str, float]] = {}

    # Helper to fetch a child's flat comp (either leaf stock or already-flattened portfolio)
    def child_comp(name: str) -> Dict[str, float] | None:
        if name in portfolios:
            return flattened.get(name)  # may be None if not yet expanded
        else:
            return {name: 1.0}  # leaf stock

    remaining = set(portfolios)
    while remaining:
        progressed = False
        for p in list(remaining):
            comp: Dict[str, float] = {}
            all_ready = True
            for child_name, w in children[p]:
                cc = child_comp(child_name)
                if cc is None:  # child portfolio not flattened yet
                    all_ready = False
                    break
                for stock, sw in cc.items():
                    comp[stock] = comp.get(stock, 0.0) + w * sw
            if all_ready:
                flattened[p] = comp
                remaining.remove(p)
                progressed = True
        if not progressed:
            # We couldn't expand any remaining portfolio -> there is a cycle or forward ref loop.
            cycle_list = ", ".join(sorted(remaining))
            raise ValueError(f"Cannot resolve portfolios (cycle or unresolved refs): {cycle_list}")

    return flattened


def stream_and_write(
    flattened: Dict[str, Dict[str, float]],
    prices_csv: str,
    output_csv: str,
) -> None:
    """
    Stream prices.csv and write:
      - each input tick (NAME, PRICE)
      - then any portfolio rows whose values are computable AND changed since last tick
    Simplicity over performance: recompute all portfolio values every tick.
    """
    seen_prices: Dict[str, float] = {}
    last_values: Dict[str, float] = {}

    with open(prices_csv, newline="", encoding="utf-8") as fin, \
         open(output_csv, "w", newline="", encoding="utf-8") as fout:

        rin = csv.reader(fin)
        header = next(rin, None)
        if header is None or header != ["NAME", "PRICE"]:
            raise ValueError("prices.csv must start with header: NAME,PRICE")

        wout = csv.writer(fout)
        wout.writerow(["NAME", "PRICE"])

        for i, (name, price_str) in enumerate(rin, start=2):
            name = name.strip()
            price = float(price_str)  # parse as double

            # 1) Write the raw tick
            wout.writerow([name, price])

            # 2) Update seen price
            seen_prices[name] = price

            # 3) Recompute all portfolios this tick (simple and clear)
            for p, comp in flattened.items():
                # Only price if all required stocks are known
                all_known = all((stk in seen_prices) for stk in comp.keys())
                if not all_known:
                    continue
                val = 0.0
                for stk, w in comp.items():
                    val += w * seen_prices[stk]
                # Emit only if first time or changed
                if (p not in last_values) or (val != last_values[p]):
                    wout.writerow([p, f"{val:.10g}"])
                last_values[p] = val


def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    children = read_portfolios_csv(portfolios_csv)
    flattened = expand_flattened(children)
    stream_and_write(flattened, prices_csv, output_csv)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python simple_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
