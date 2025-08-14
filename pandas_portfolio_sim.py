from __future__ import annotations
import sys
import math
import csv
from typing import Dict, List, Tuple, Set, Optional
import pandas as pd

def read_portfolios_csv(path: str) -> Dict[str, List[Tuple[str, float]]]:
    df = pd.read_csv(path, dtype={"NAME": str, "SHARES": str})
    if list(df.columns) != ["NAME", "SHARES"]:
        raise ValueError("portfolios.csv must have columns exactly: NAME,SHARES")

    portfolio_components: Dict[str, Dict[str, float]] = {}
    current_portfolio: Optional[str] = None

    for row_index, row_data in df.iterrows():
        entry_name = str(row_data["NAME"]).strip()
        shares_value_raw = row_data["SHARES"]
        is_portfolio_header = pd.isna(shares_value_raw) or str(shares_value_raw).strip() == ""

        if is_portfolio_header:
            current_portfolio = entry_name
            if current_portfolio not in portfolio_components:
                portfolio_components[current_portfolio] = {}
        else:
            if current_portfolio is None:
                raise ValueError(f"Found constituent before any portfolio header at row {row_index+2}")
            shares_quantity = float(str(shares_value_raw).strip())
            previous_quantity = portfolio_components[current_portfolio].get(entry_name, 0.0)
            portfolio_components[current_portfolio][entry_name] = previous_quantity + shares_quantity

    return {p: list(components.items()) for p, components in portfolio_components.items()}

def flatten_to_stocks(portfolio_components: Dict[str, List[Tuple[str, float]]]) -> Dict[str, Dict[str, float]]:
    portfolio_names: Set[str] = set(portfolio_components.keys())
    memoized_weights: Dict[str, Dict[str, float]] = {}
    currently_visiting: Set[str] = set()

    def dfs(current_node: str) -> Dict[str, float]:
        if current_node in memoized_weights:
            return memoized_weights[current_node]
        if current_node in currently_visiting:
            raise ValueError(f"Cycle detected at '{current_node}'")
        if current_node not in portfolio_names:
            memoized_weights[current_node] = {current_node: 1.0}  # leaf stock
            return memoized_weights[current_node]

        currently_visiting.add(current_node)
        accumulated_weights: Dict[str, float] = {}
        for component_name, component_weight in portfolio_components[current_node]:
            sub_weights = dfs(component_name)
            for stock_name, stock_weight in sub_weights.items():
                accumulated_weights[stock_name] = accumulated_weights.get(stock_name, 0.0) + component_weight * stock_weight
        currently_visiting.remove(current_node)
        memoized_weights[current_node] = accumulated_weights
        return accumulated_weights

    flattened_portfolios: Dict[str, Dict[str, float]] = {}
    for portfolio_name in portfolio_names:
        flattened_portfolios[portfolio_name] = dfs(portfolio_name)
    return flattened_portfolios

def flattened_to_df(flattened_portfolios: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    rows = []
    for portfolio_name, stock_weights in flattened_portfolios.items():
        for stock_name, weight in stock_weights.items():
            rows.append((portfolio_name, stock_name, float(weight)))
    return pd.DataFrame(rows, columns=["portfolio", "stock", "weight"])

class PortfolioRuntime:
    def __init__(self, flattened_df: pd.DataFrame):
        if set(flattened_df.columns) != {"portfolio", "stock", "weight"}:
            raise ValueError("flattened_df must have columns: portfolio, stock, weight")

        self.required_stock_counts: pd.Series = (
            flattened_df.groupby("portfolio")["stock"].nunique().astype("int64")
        )
        self.current_portfolio_value: pd.Series = pd.Series(0.0, index=self.required_stock_counts.index, dtype="float64")
        self.seen_stock_counts: pd.Series = pd.Series(0, index=self.required_stock_counts.index, dtype="int64")

        self.stock_to_portfolios_map: Dict[str, pd.DataFrame] = {
            stock: sub_df[["portfolio", "weight"]].reset_index(drop=True)
            for stock, sub_df in flattened_df.groupby("stock", sort=False)
        }
        self.stock_price_cache: Dict[str, float] = {}

    def on_price(self, stock_name: str, asset_price: float):
        impacted_portfolios = self.stock_to_portfolios_map.get(stock_name)
        if impacted_portfolios is None or impacted_portfolios.empty:
            self.stock_price_cache[stock_name] = asset_price
            return []

        completed_updates = []
        is_first_price_update = stock_name not in self.stock_price_cache
        if is_first_price_update:
            portfolio_names = impacted_portfolios["portfolio"].values
            weights = impacted_portfolios["weight"].values
            value_increment = weights * asset_price

            self.current_portfolio_value.loc[portfolio_names] += value_increment
            self.seen_stock_counts.loc[portfolio_names] += 1

            newly_completed_mask = self.seen_stock_counts.loc[portfolio_names] == self.required_stock_counts.loc[portfolio_names]
            if newly_completed_mask.any():
                for portfolio_name in impacted_portfolios.loc[newly_completed_mask.values, "portfolio"]:
                    completed_updates.append((portfolio_name, float(self.current_portfolio_value.loc[portfolio_name])))
        else:
            old_price = self.stock_price_cache[stock_name]
            price_delta = asset_price - old_price
            if not math.isclose(price_delta, 0.0):
                portfolio_names = impacted_portfolios["portfolio"].values
                weights = impacted_portfolios["weight"].values
                value_increment = weights * price_delta
                self.current_portfolio_value.loc[portfolio_names] += value_increment

                already_completed_mask = (
                    self.seen_stock_counts.loc[portfolio_names].values == self.required_stock_counts.loc[portfolio_names].values
                )
                if already_completed_mask.any():
                    for portfolio_name in impacted_portfolios.loc[pd.Series(already_completed_mask).values, "portfolio"]:
                        completed_updates.append((portfolio_name, float(self.current_portfolio_value.loc[portfolio_name])))

        self.stock_price_cache[stock_name] = asset_price
        completed_updates.sort(key=lambda x: x[0])
        return completed_updates

def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    portfolio_components = read_portfolios_csv(portfolios_csv)
    flattened_portfolios = flatten_to_stocks(portfolio_components)
    flattened_df = flattened_to_df(flattened_portfolios)
    runtime = PortfolioRuntime(flattened_df)

    with open(output_csv, "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["NAME", "PRICE"])

        price_chunk_iter = pd.read_csv(prices_csv, dtype={"NAME": str, "PRICE": float}, chunksize=1)
        for price_chunk in price_chunk_iter:
            price_row = price_chunk.iloc[0]
            asset_name = str(price_row["NAME"]).strip()
            asset_price = float(price_row["PRICE"])
            writer.writerow([asset_name, asset_price])

            for (portfolio_name, portfolio_value) in runtime.on_price(asset_name, asset_price):
                writer.writerow([portfolio_name, f"{portfolio_value:.10g}"])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python pandas_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
