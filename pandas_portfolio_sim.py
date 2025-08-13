from __future__ import annotations
import sys
import math
import csv
from typing import Dict, List, Tuple, Set
import pandas as pd

def read_portfolios_csv(path: str) -> Dict[str, List[Tuple[str, float]]]:
    df = pd.read_csv(path, dtype={"NAME": str, "SHARES": str})
    if list(df.columns) != ["NAME", "SHARES"]:
        raise ValueError("portfolios.csv must have columns exactly: NAME,SHARES")

    children: Dict[str, Dict[str, float]] = {}
    current: str | None = None

    for i, row in df.iterrows():
        name = str(row["NAME"]).strip()
        shares_raw = row["SHARES"]
        shares_is_blank = pd.isna(shares_raw) or str(shares_raw).strip() == ""

        if shares_is_blank:
            current = name
            if current not in children:
                children[current] = {}
        else:
            if current is None:
                raise ValueError(f"Found constituent before any portfolio header at row {i+2}")
            qty = float(str(shares_raw).strip())
            prev = children[current].get(name, 0.0)
            children[current][name] = prev + qty

    return {p: list(d.items()) for p, d in children.items()}

def flatten_to_stocks(children: Dict[str, List[Tuple[str, float]]]) -> Dict[str, Dict[str, float]]:
    portfolios: Set[str] = set(children.keys())
    memo: Dict[str, Dict[str, float]] = {}
    visiting: Set[str] = set()

    def dfs(name: str) -> Dict[str, float]:
        if name in memo:
            return memo[name]
        if name in visiting:
            raise ValueError(f"Cycle detected at '{name}'")
        if name not in portfolios:
            memo[name] = {name: 1.0}  # leaf stock
            return memo[name]

        visiting.add(name)
        acc: Dict[str, float] = {}
        for child, w in children[name]:
            sub = dfs(child)
            for stock, sw in sub.items():
                acc[stock] = acc.get(stock, 0.0) + w * sw
        visiting.remove(name)
        memo[name] = acc
        return acc

    flattened: Dict[str, Dict[str, float]] = {}
    for p in portfolios:
        flattened[p] = dfs(p)
    return flattened

def flattened_to_df(flattened: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    rows = []
    for p, comp in flattened.items():
        for s, w in comp.items():
            rows.append((p, s, float(w)))
    return pd.DataFrame(rows, columns=["portfolio", "stock", "weight"])

class PortfolioRuntime:
    def __init__(self, flattened_df: pd.DataFrame):
        if set(flattened_df.columns) != {"portfolio", "stock", "weight"}:
            raise ValueError("flattened_df must have columns: portfolio, stock, weight")

        self.need_counts: pd.Series = (
            flattened_df.groupby("portfolio")["stock"].nunique().astype("int64")
        )
        self.running_value: pd.Series = pd.Series(0.0, index=self.need_counts.index, dtype="float64")
        self.seen_counts: pd.Series = pd.Series(0, index=self.need_counts.index, dtype="int64")

        self.rev_dep_groups: Dict[str, pd.DataFrame] = {
            stock: sub[["portfolio", "weight"]].reset_index(drop=True)
            for stock, sub in flattened_df.groupby("stock", sort=False)
        }
        self.seen_prices: Dict[str, float] = {}

    def on_price(self, stock: str, price: float):
        sub = self.rev_dep_groups.get(stock)
        if sub is None or sub.empty:
            self.seen_prices[stock] = price
            return []

        out = []
        first_time = stock not in self.seen_prices
        if first_time:
            p_index = sub["portfolio"].values
            w = sub["weight"].values
            incr = w * price

            self.running_value.loc[p_index] = self.running_value.loc[p_index].values + incr
            self.seen_counts.loc[p_index] = self.seen_counts.loc[p_index].values + 1

            just_complete = self.seen_counts.loc[p_index] == self.need_counts.loc[p_index]
            if just_complete.any():
                for p in sub.loc[just_complete.values, "portfolio"]:
                    out.append((p, float(self.running_value.loc[p])))
        else:
            old = self.seen_prices[stock]
            delta = price - old
            if not math.isclose(delta, 0.0):
                p_index = sub["portfolio"].values
                w = sub["weight"].values
                incr = w * delta
                self.running_value.loc[p_index] = self.running_value.loc[p_index].values + incr

                complete_mask = (
                    self.seen_counts.loc[p_index].values == self.need_counts.loc[p_index].values
                )
                if complete_mask.any():
                    for p in sub.loc[pd.Series(complete_mask).values, "portfolio"]:
                        out.append((p, float(self.running_value.loc[p])))

        self.seen_prices[stock] = price
        out.sort(key=lambda x: x[0])
        return out

def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    children = read_portfolios_csv(portfolios_csv)
    flattened = flatten_to_stocks(children)
    flat_df = flattened_to_df(flattened)
    runtime = PortfolioRuntime(flat_df)

    with open(output_csv, "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["NAME", "PRICE"])

        it = pd.read_csv(prices_csv, dtype={"NAME": str, "PRICE": float}, chunksize=1)
        for chunk in it:
            row = chunk.iloc[0]
            name = str(row["NAME"]).strip()
            price = float(row["PRICE"])
            writer.writerow([name, price])

            for (pname, pval) in runtime.on_price(name, price):
                writer.writerow([pname, f"{pval:.10g}"])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python pandas_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
