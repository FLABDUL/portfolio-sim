from __future__ import annotations

import csv
import math
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

import polars as pl

COL_NAME = "NAME"
COL_SHARES = "SHARES"
COL_PRICE = "PRICE"
COL_PORTFOLIO = "portfolio"
COL_STOCK = "stock"
COL_WEIGHT = "weight"

CSV_HEADER_OUTPUT = [COL_NAME, COL_PRICE]
CSV_HEADER_FLATTENED = [COL_PORTFOLIO, COL_STOCK, COL_WEIGHT]

@dataclass(frozen=True)
class Component:
    name: str
    shares: float

@dataclass(frozen=True)
class Portfolio:
    name: str
    components: list[Component]

@dataclass
class ComponentMap:
    items: dict[str, list[Component]] = field(default_factory=dict)

    def add_component(self, portfolio: str, component: Component):
        if portfolio not in self.items:
            self.items[portfolio] = []

        for i, c in enumerate(self.items[portfolio]):
            if c.name == component.name:
                new_total = c.shares + component.shares
                self.items[portfolio][i] = Component(c.name, new_total)
                return

        self.items[portfolio].append(component)

    def to_portfolio_collection(self) -> PortfolioCollection:
        return PortfolioCollection({
            name: Portfolio(name, components)
            for name, components in self.items.items()
        })

@dataclass
class PortfolioCollection(Mapping[str, Portfolio]):
    items: dict[str, Portfolio]

    def names(self) -> set[str]:
        return set(self.items.keys())

    def __getitem__(self, name: str) -> Portfolio:
        return self.items[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

@dataclass
class FlattenedPortfolioCollection(Mapping[str, dict[str, float]]):
    weights_by_portfolio: dict[str, dict[str, float]]

    def to_dataframe(self) -> pl.DataFrame:
        rows = []
        for portfolio_name, stock_weights in self.weights_by_portfolio.items():
            for stock_name, weight in stock_weights.items():
                rows.append((portfolio_name, stock_name, float(weight)))
        return pl.DataFrame(rows, schema=CSV_HEADER_FLATTENED)

    def __getitem__(self, name: str) -> dict[str, float]:
        return self.weights_by_portfolio[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.weights_by_portfolio)

    def __len__(self) -> int:
        return len(self.weights_by_portfolio)

@dataclass
class CycleTracker:
    visiting: set[str] = field(default_factory=set)

    def add(self, name: str):
        self.visiting.add(name)

    def remove(self, name: str):
        self.visiting.remove(name)

    def __contains__(self, name: str) -> bool:
        return name in self.visiting

@dataclass(frozen=True)
class StockToPortfoliosMap:
    mapping: dict[str, pl.DataFrame]

    def get(self, stock: str) -> pl.DataFrame | None:
        return self.mapping.get(stock)

@dataclass
class PriceCache:
    prices: dict[str, float] = field(default_factory=dict)

    def update(self, stock: str, price: float):
        self.prices[stock] = price

    def get(self, stock: str) -> float | None:
        return self.prices.get(stock)

    def __contains__(self, stock: str) -> bool:
        return stock in self.prices

class CycleDetectedError(ValueError):
    """Raised when a cycle is detected in portfolio resolution."""

    def __init__(self, portfolio_name: str):
        msg = f"Cycle detected at '{portfolio_name}'"
        super().__init__(msg)

def read_portfolios_csv(path: str) -> PortfolioCollection:
    df = pl.read_csv(path).with_columns([
        pl.col(COL_NAME).cast(pl.Utf8),
        pl.col(COL_SHARES).cast(pl.Utf8),
    ])

    component_map = ComponentMap()
    current_portfolio: str | None = None

    for row in df.iter_rows(named=True):
        entry_name = row[COL_NAME].strip()
        shares_value_raw = row[COL_SHARES]
        is_portfolio_header = shares_value_raw is None or str(shares_value_raw).strip() == ""

        if is_portfolio_header:
            current_portfolio = entry_name
        else:
            shares_quantity = float(shares_value_raw)
            component_map.add_component(current_portfolio, Component(entry_name, shares_quantity))

    return component_map.to_portfolio_collection()

def flatten_to_stocks(portfolios: PortfolioCollection) -> FlattenedPortfolioCollection:
    memoized_weights: dict[str, dict[str, float]] = {}
    visiting = CycleTracker()

    def dfs(current_node: str) -> dict[str, float]:
        if current_node in memoized_weights:
            return memoized_weights[current_node]
        if current_node in visiting:
            raise CycleDetectedError(current_node)
        if current_node not in portfolios.names():
            memoized_weights[current_node] = {current_node: 1.0}
            return memoized_weights[current_node]

        visiting.add(current_node)
        accumulated_weights: dict[str, float] = {}
        for component in portfolios[current_node].components:
            sub_weights = dfs(component.name)
            for stock_name, stock_weight in sub_weights.items():
                accumulated_weights[stock_name] = accumulated_weights.get(stock_name, 0.0) + component.shares * stock_weight
        visiting.remove(current_node)
        memoized_weights[current_node] = accumulated_weights
        return accumulated_weights

    flattened_portfolios: dict[str, dict[str, float]] = {}
    for portfolio_name in portfolios.names():
        flattened_portfolios[portfolio_name] = dfs(portfolio_name)
    return FlattenedPortfolioCollection(flattened_portfolios)

class PortfolioRuntime:
    def __init__(self, flattened_df: pl.DataFrame):
        grouped = (
            flattened_df.group_by(COL_PORTFOLIO)
            .agg(pl.col(COL_STOCK).n_unique().alias("required"))
            .sort(COL_PORTFOLIO)
        )

        df_counts = grouped.to_pandas().set_index(COL_PORTFOLIO)
        df_counts.index.name = None  # optional: remove index name for consistency

        self._required_stock_counts = df_counts["required"]
        self._current_portfolio_value = pd.Series(0.0, index=self._required_stock_counts.index, dtype="float64")
        self._seen_stock_counts = pd.Series(0, index=self._required_stock_counts.index, dtype="int64")

        self._stock_to_portfolios_map = StockToPortfoliosMap({
            stock: sub_df.select([COL_PORTFOLIO, COL_WEIGHT]).sort(COL_PORTFOLIO)
            for stock, sub_df in flattened_df.group_by(COL_STOCK, maintain_order=True)
        })
        self._stock_price_cache = PriceCache()

    def on_price(self, stock_name: str, asset_price: float) -> None:
        impacted_portfolios = self._stock_to_portfolios_map.get(stock_name)
        if impacted_portfolios is None or impacted_portfolios.is_empty():
            self._stock_price_cache.update(stock_name, asset_price)
            return []

        completed_updates = []
        is_first_price_update = stock_name not in self._stock_price_cache
        portfolio_names = impacted_portfolios[COL_PORTFOLIO].to_list()
        weights = impacted_portfolios[COL_WEIGHT].to_numpy()

        if is_first_price_update:
            value_increment = weights * asset_price
            for i, name in enumerate(portfolio_names):
                self._current_portfolio_value.loc[name] += value_increment[i]
                self._seen_stock_counts.loc[name] += 1

            newly_completed = [name for name in portfolio_names if self._seen_stock_counts.loc[name] == self._required_stock_counts.loc[name]]
            for name in newly_completed:
                completed_updates.append((name, float(self._current_portfolio_value.loc[name])))

        else:
            old_price = self._stock_price_cache.get(stock_name)
            price_delta = asset_price - old_price
            if not math.isclose(price_delta, 0.0):
                value_increment = weights * price_delta
                for i, name in enumerate(portfolio_names):
                    self._current_portfolio_value.loc[name] += value_increment[i]

                already_completed = [name for name in portfolio_names if self._seen_stock_counts.loc[name] == self._required_stock_counts.loc[name]]
                for name in already_completed:
                    completed_updates.append((name, float(self._current_portfolio_value.loc[name])))

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

        price_chunk_iter = pl.read_csv(prices_csv, dtypes={COL_NAME: pl.Utf8, COL_PRICE: pl.Float64}).iter_rows(
            named=True)
        for row in price_chunk_iter:
            asset_name = str(row[COL_NAME]).strip()
            asset_price = float(row[COL_PRICE])
            writer.writerow([asset_name, asset_price])

            for (portfolio_name, portfolio_value) in runtime.on_price(asset_name, asset_price):
                writer.writerow([portfolio_name, f"{portfolio_value:.10g}"])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python pandas_portfolio_sim.py portfolios.csv prices.csv portfolio_prices.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
