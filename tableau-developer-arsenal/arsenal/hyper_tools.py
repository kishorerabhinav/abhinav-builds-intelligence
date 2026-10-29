"""Build .hyper extracts from CSV files or pandas DataFrames.

Needs the optional dependencies: pip install -e ".[hyper]"
"""

from __future__ import annotations

from pathlib import Path


def _hyper():
    try:
        import pandas as pd
        from tableauhyperapi import (
            Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition, TableName, Telemetry,
        )
    except ImportError as exc:
        raise SystemExit('Hyper tools need: pip install -e ".[hyper]"') from exc
    return locals()


def dataframe_to_hyper(df, dest: str | Path, table: str = "Extract") -> Path:
    h = _hyper()
    pd = h["pd"]
    SqlType, TableDefinition = h["SqlType"], h["TableDefinition"]

    def sql_type(series):
        if pd.api.types.is_bool_dtype(series):
            return SqlType.bool()
        if pd.api.types.is_integer_dtype(series):
            return SqlType.big_int()
        if pd.api.types.is_float_dtype(series):
            return SqlType.double()
        if pd.api.types.is_datetime64_any_dtype(series):
            return SqlType.timestamp()
        return SqlType.text()

    # Tableau's own extracts use "Extract"."Extract", so this opens like a native extract.
    table_def = TableDefinition(
        table_name=h["TableName"]("Extract", table),
        columns=[TableDefinition.Column(str(c), sql_type(df[c])) for c in df.columns],
    )
    rows = df.astype(object).where(df.notna(), None).values.tolist()

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with h["HyperProcess"](telemetry=h["Telemetry"].DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with h["Connection"](hyper.endpoint, dest, h["CreateMode"].CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema_if_not_exists("Extract")
            conn.catalog.create_table(table_def)
            with h["Inserter"](conn, table_def) as inserter:
                inserter.add_rows(rows)
                inserter.execute()
    return dest


def csv_to_hyper(csv: str | Path, dest: str | Path | None = None, parse_dates: list[str] | None = None) -> Path:
    pd = _hyper()["pd"]
    csv = Path(csv)
    df = pd.read_csv(csv, parse_dates=parse_dates or [])
    return dataframe_to_hyper(df, dest or csv.with_suffix(".hyper"))
