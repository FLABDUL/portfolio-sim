import csv
from pathlib import Path
import super_simple_portfolio_sim as sim


def write_csv(path: Path, rows):
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_csv_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_basic_end_to_end(tmp_path: Path):
    # portfolios.csv
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
            "NVDA,300",
            "AUTOS,",
            "FORD,100",
            "TSLA,200",
            "BMW,200",
            "INDUSTRIALS,",
            "TECH,2",
            "AUTOS,3",
        ],
    )

    # prices.csv (enough to compute all portfolios once)
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "AAPL,173",
            "MSFT,425",
            "NVDA,880",
            "FORD,12",
            "TSLA,250",
            "BMW,80",
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))

    rows = read_csv_rows(out)
    assert rows[0] == ["NAME", "PRICE"]

    # Known values
    tech_val = 100*173 + 200*425 + 300*880  # 366300
    autos_val = 100*12 + 200*250 + 200*80   # 67200
    industrials_val = 2*tech_val + 3*autos_val  # 934200

    assert ["TECH", str(tech_val)] in rows
    assert ["AUTOS", str(autos_val)] in rows
    assert ["INDUSTRIALS", str(industrials_val)] in rows


def test_update_triggers_new_output(tmp_path: Path):
    # portfolios.csv
    write_csv(
        tmp_path / "portfolios.csv",
        [
            "NAME,SHARES",
            "TECH,",
            "AAPL,100",
            "MSFT,200",
        ],
    )

    # prices.csv (update AAPL after both stocks priced)
    write_csv(
        tmp_path / "prices.csv",
        [
            "NAME,PRICE",
            "AAPL,10",
            "MSFT,5",
            "AAPL,11",  # update
        ],
    )

    out = tmp_path / "portfolio_prices.csv"
    sim.main(str(tmp_path / "portfolios.csv"), str(tmp_path / "prices.csv"), str(out))
    rows = read_csv_rows(out)

    # First TECH = 100*10 + 200*5 = 2000
    # After AAPL=11, TECH = 100*11 + 200*5 = 2100
    assert ["TECH", "2000"] in rows
    assert ["TECH", "2100"] in rows
