"""H&M purchase data: typed loading with a parquet cache keyed by source sha256, the chronological split
(final week test, prior week validation, earlier training), the Gen Z cohort and owned-before-cutoff (P0387-P0388)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..core import RESEARCH, Split

CACHE = RESEARCH / ".cache"


def _cached(path: Path, sha: str, reader) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{path.stem}-{sha[:16]}.parquet"
    if target.exists():
        return pd.read_parquet(target)
    df = reader(path)
    df.to_parquet(target, index=False)
    return df


def load_transactions(path: Path, sha: str) -> pd.DataFrame:
    def read(p):
        df = pd.read_csv(p, dtype={"customer_id": "string", "article_id": "string", "price": "float32",
                                   "sales_channel_id": "int8"}, parse_dates=["t_dat"])
        return df[["t_dat", "customer_id", "article_id", "price", "sales_channel_id"]]
    return _cached(path, sha, read)


def load_customers(path: Path, sha: str) -> pd.DataFrame:
    return _cached(path, sha, lambda p: pd.read_csv(p, dtype={"customer_id": "string"}, usecols=["customer_id", "age"]))


def load_articles(path: Path, sha: str) -> pd.DataFrame:
    return _cached(path, sha, lambda p: pd.read_csv(p, dtype=str, keep_default_na=False))


@dataclass(frozen=True)
class TimeSplit:
    train: Split
    validation: Split
    test: Split
    validation_start: pd.Timestamp
    test_start: pd.Timestamp
    end: pd.Timestamp


def chronological_split(tx: pd.DataFrame, week_days: int = 7) -> TimeSplit:
    end = tx["t_dat"].max().normalize()
    test_start = end - pd.Timedelta(days=week_days - 1)
    val_start = test_start - pd.Timedelta(days=week_days)
    train = tx[tx["t_dat"] < val_start]
    val = tx[(tx["t_dat"] >= val_start) & (tx["t_dat"] < test_start)]
    test = tx[tx["t_dat"] >= test_start]
    # leakage assertions: strictly ordered, disjoint, complete
    assert train["t_dat"].max() < val_start <= val["t_dat"].min() if len(val) else True
    assert val["t_dat"].max() < test_start <= test["t_dat"].min() if len(test) else True
    assert len(train) + len(val) + len(test) == len(tx)
    return TimeSplit(Split("train", train, "before validation week"), Split("validation", val, "week before test"),
                     Split("test", test, "final week"), val_start, test_start, end)


def genz_cohort(customers: pd.DataFrame, evaluated: pd.DataFrame, max_age: int = 23) -> tuple[list[str], dict]:
    """Customers aged <= max_age (Sept 2020) with >= 1 purchase in the evaluated week; missing ages excluded+counted."""
    buyers = set(evaluated["customer_id"].unique())
    c = customers[customers["customer_id"].isin(buyers)]
    missing = int(c["age"].isna().sum())
    genz = c[(c["age"].notna()) & (c["age"] <= max_age)]["customer_id"].tolist()
    return sorted(genz), {"buyers_in_week": len(buyers), "missing_age_excluded": missing,
                          "genz_evaluated": len(genz), "max_age": max_age}


def purchases_by_customer(tx: pd.DataFrame) -> dict[str, set[str]]:
    return {c: set(a) for c, a in tx.groupby("customer_id", sort=False)["article_id"]}


def owned_before(tx: pd.DataFrame, cutoff: pd.Timestamp, customers: list[str]) -> dict[str, set[str]]:
    """'Owned items' = everything bought before the evaluated week (P0388). Never includes the evaluated week."""
    past = tx[(tx["t_dat"] < cutoff) & (tx["customer_id"].isin(set(customers)))]
    assert past["t_dat"].max() < cutoff if len(past) else True
    owned = purchases_by_customer(past)
    return {c: owned.get(c, set()) for c in customers}
