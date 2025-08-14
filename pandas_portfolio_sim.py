from __future__ import annotations
import sys
import math
import csv
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Iterator
import pandas as pd

# Column constants
COL_NAME = "NAME"
COL_SHARES = "SHARES"
COL_PRICE = "PRICE"
COL_PORTFOLIO = "portfolio"
COL_STOCK = "stock"
COL_WEIGHT = "weight"

CSV_HEADER_OUTPUT = [COL_NAME, COL_PRICE]
CSV_HEADER_FLATTENED = [COL_PORTFOLIO, COL_STOCK, COL_WEIGHT]

@dataclass
class Component:
    name: str
    shares: float

@dataclass
class Portfolio:
    name: str
    components: List[Component]

@dataclass
class ComponentMap:
    items: Dict[str, List[Component]] = field(default_factory=dict)

    def add_component(self, portfolio: str, component: Component):
        if portfolio not in self.items:
            self.items[portfolio] = []
        for c in self.items[portfolio]:
            if c.name == component.name:
                c.shares += component.shares
                return
        self.items[portfolio].append(component)

    def to_portfolio_collection(self) -> PortfolioCollection:
        return PortfolioCollection({
            name: Portfolio(name, components)
            for name, components in self.items.items()
        })

@dataclass
class PortfolioCollection:
    items: Dict[str, Portfolio]

    def names(self) -> Set[str]:
        return set(self.items.keys())

    def __getitem__(self, name: str) -> Portfolio:
        return self.items[name]

    def __iter__(self) -> Iterator[tuple[str, Portfolio]]:
        return iter(self.items.items())

@dataclass
class FlattenedPortfolioCollection:
    weights_by_portfolio: Dict[str, Dict[str, float]]

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for portfolio_name, stock_weights in self.weights_by_portfolio.items():
            for stock_name, weight in stock_weights.items():
                rows.append((portfolio_name, stock_name, float(weight)))
        return pd.DataFrame(rows, columns=CSV_HEADER_FLATTENED)

    def __getitem__(self, name: str) -> Dict[str, float]:
        return self.weights_by_portfolio[name]

    def __iter__(self) -> Iterator[tuple[str, Dict[str, float]]]:
        return iter(self.weights_by_portfolio.items())

@dataclass
class MemoizedWeights:
    items: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def __contains__(self, key: str) -> bool:
        return key in self.items

    def __getitem__(self, key: str) -> Dict[str, float]:
        return self.items[key]

    def __setitem__(self, key: str, value: Dict[str, float]):
        self.items[key] = value

@dataclass
class CycleTracker:
    visiting: Set[str] = field(default_factory=set)

    def add(self, name: str):
        self.visiting.add(name)

    def remove(self, name: str):
        self.visiting.remove(name)

    def __contains__(self, name: str) -> bool:
        return name in self.visiting

@dataclass
class StockToPortfoliosMap:
    mapping: Dict[str, pd.DataFrame]

    def get(self, stock: str) -> Optional[pd.DataFrame]:
        return self.mapping.get(stock)

@dataclass
class PriceCache:
    prices: Dict[str, float] = field(default_factory=dict)

    def update(self, stock: str, price: float):
        self.prices[stock] = price

    def get(self, stock: str) -> Optional[float]:
        return self.prices.get(stock)

    def __contains__(self, stock: str) -> bool:
        return stock in self.prices

def read_portfolios_csv(path: str) -> PortfolioCollection:
    df = pd.read_csv(path, dtype={COL_NAME: str, COL_SHARES: str})

    component_map = ComponentMap()
    current_portfolio: Optional[str] = None

    for _, row in enumerate(df.itertuples(index=False)):
        entry_name = str(getattr(row, COL_NAME)).strip()
        shares_value_raw = getattr(row, COL_SHARES)
        is_portfolio_header = pd.isna(shares_value_raw) or str(shares_value_raw).strip() == ""

        if is_portfolio_header:
            current_portfolio = entry_name
        else:
            shares_quantity = float(shares_value_raw)
            component_map.add_component(current_portfolio, Component(entry_name, shares_quantity))

    return component_map.to_portfolio_collection()

def flatten_to_stocks(portfolios: PortfolioCollection) -> FlattenedPortfolioCollection:
    memoized_weights = MemoizedWeights()
    visiting = CycleTracker()

    def dfs(current_node: str) -> Dict[str, float]:
        if current_node in memoized_weights:
            return memoized_weights[current_node]
        if current_node in visiting:
            raise ValueError(f"Cycle detected at '{current_node}'")
        if current_node not in portfolios.names():
            memoized_weights[current_node] = {current_node: 1.0}
            return memoized_weights[current_node]

        visiting.add(current_node)
        accumulated_weights: Dict[str, float] = {}
        for component in portfolios[current_node].components:
            sub_weights = dfs(component.name)
            for stock_name, stock_weight in sub_weights.items():
                accumulated_weights[stock_name] = accumulated_weights.get(stock_name, 0.0) + component.shares * stock_weight
        visiting.remove(current_node)
        memoized_weights[current_node] = accumulated_weights
        return accumulated_weights

    flattened_portfolios: Dict[str, Dict[str, float]] = {}
    for portfolio_name in portfolios.names():
        flattened_portfolios[portfolio_name] = dfs(portfolio_name)
    return FlattenedPortfolioCollection(flattened_portfolios)

class PortfolioRuntime:
    def __init__(self, flattened_df: pd.DataFrame):
        self._required_stock_counts: pd.Series = (
            flattened_df.groupby(COL_PORTFOLIO)[COL_STOCK].nunique().astype("int64")
        )
        self._current_portfolio_value: pd.Series = pd.Series(
            0.0, index=self._required_stock_counts.index, dtype="float64"
        )
        self._seen_stock_counts: pd.Series = pd.Series(
            0, index=self._required_stock_counts.index, dtype="int64"
        )

        self._stock_to_portfolios_map = StockToPortfoliosMap({
            stock: sub_df[[COL_PORTFOLIO, COL_WEIGHT]].reset_index(drop=True)
            for stock, sub_df in flattened_df.groupby(COL_STOCK, sort=False)
        })
        self._stock_price_cache = PriceCache()

    def on_price(self, stock_name: str, asset_price: float):
        impacted_portfolios = self._stock_to_portfolios_map.get(stock_name)
        if impacted_portfolios is None or impacted_portfolios.empty:
            self._stock_price_cache.update(stock_name, asset_price)
            return []

        completed_updates = []
        is_first_price_update = stock_name not in self._stock_price_cache
        portfolio_names = impacted_portfolios[COL_PORTFOLIO].values
        weights = impacted_portfolios[COL_WEIGHT].values

        if is_first_price_update:
            value_increment = weights * asset_price
            self._current_portfolio_value.loc[portfolio_names] += value_increment
            self._seen_stock_counts.loc[portfolio_names] += 1

            newly_completed_mask = (
                self._seen_stock_counts.loc[portfolio_names] ==
                self._required_stock_counts.loc[portfolio_names]
            )

            if newly_completed_mask.any():
                for portfolio_name in impacted_portfolios.loc[newly_completed_mask.values, COL_PORTFOLIO]:
                    completed_updates.append((portfolio_name, float(self._current_portfolio_value.loc[portfolio_name])))

        else:
            old_price = self._stock_price_cache.get(stock_name)
            price_delta = asset_price - old_price
            if not math.isclose(price_delta, 0.0):
                value_increment = weights * price_delta
                self._current_portfolio_value.loc[portfolio_names] += value_increment

                already_completed_mask = (
                    self._seen_stock_counts.loc[portfolio_names].values ==
                    self._required_stock_counts.loc[portfolio_names].values
                )

                if already_completed_mask.any():
                    for portfolio_name in impacted_portfolios.loc[pd.Series(already_completed_mask).values, COL_PORTFOLIO]:
                        completed_updates.append((portfolio_name, float(self._current_portfolio_value.loc[portfolio_name])))

        self._stock_price_cache.update(stock_name, asset_price)
        completed_updates.sort(key=lambda x: x[0])
        return completed_updates

def main(portfolios_csv: str, prices_csv: str, output_csv: str) -> None:
    portfolio_collection = read_portfolios_csv(portfolios_csv)
    flattened_portfolios = flatten_to_stocks(portfolio_collection)
    flattened_df = flattened_portfolios.to_dataframe()
    runtime = PortfolioRuntime(flattened_df)

    with open(output_csv, "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(CSV_HEADER_OUTPUT)

        price_chunk_iter = pd.read_csv(prices_csv, dtype={COL_NAME: str, COL_PRICE: float}, chunksize=1)
        for price_chunk in price_chunk_iter:
            price_row = price_chunk.iloc[0]
            asset_name = str(price_row[COL_NAME]).strip()
            asset_price = float(price_row[COL_PRICE])
            writer.writerow([asset_name, asset_price])

            for (portfolio_name, portfolio_value) in runtime.on_price(asset_name, asset_price):
                writer.writerow([portfolio_name, f"{portfolio_value:.10g}"])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python pandas_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
