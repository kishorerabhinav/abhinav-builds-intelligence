"""Inspect and package .twb/.twbx files without Tableau Desktop."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def _load_twb(path: Path) -> ET.Element:
    if path.suffix.lower() == ".twbx":
        with zipfile.ZipFile(path) as zf:
            twb = next(n for n in zf.namelist() if n.lower().endswith(".twb"))
            return ET.fromstring(zf.read(twb))
    return ET.parse(path).getroot()


def inspect_workbook(path: str | Path) -> dict:
    """Summarise data sources, calculated fields, worksheets and dashboards."""
    root = _load_twb(Path(path))
    datasources = []
    for ds in root.iter("datasource"):
        if ds.get("name") == "Parameters" or ds.find("connection") is None and not ds.findall("column"):
            continue
        connections = sorted({c.get("class") for c in ds.iter("connection") if c.get("class")})
        calcs = [
            {
                "name": (col.get("caption") or col.get("name", "")).strip("[]"),
                "formula": calc.get("formula"),
            }
            for col in ds.findall("column")
            if (calc := col.find("calculation")) is not None and calc.get("formula")
        ]
        datasources.append({
            "name": ds.get("caption") or ds.get("name"),
            "connections": [c for c in connections if c != "federated"],
            "calculated_fields": calcs,
        })
    return {
        "version": root.get("version"),
        "source_build": root.get("source-build"),
        "datasources": datasources,
        "worksheets": [w.get("name") for w in root.iter("worksheet")],
        "dashboards": [d.get("name") for d in root.iter("dashboard")],
        "parameters": [
            (c.get("caption") or c.get("name", "")).strip("[]")
            for ds in root.iter("datasource") if ds.get("name") == "Parameters"
            for c in ds.findall("column")
        ],
    }


def package_twbx(twb: str | Path, data_files: list[str | Path], dest: str | Path | None = None) -> Path:
    """Bundle a .twb with its local data files into a .twbx.

    Data files are stored under Data/<name>; repoint the workbook's connections at
    those relative paths in Tableau first, or Tableau will ask to locate them.
    """
    twb = Path(twb)
    dest = Path(dest) if dest else twb.with_suffix(".twbx")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(twb, twb.name)
        for f in map(Path, data_files):
            zf.write(f, f"Data/{f.name}")
    return dest


def find_hardcoded_paths(path: str | Path) -> list[str]:
    """List absolute file paths in connections, which break once the workbook leaves your machine."""
    root = _load_twb(Path(path))
    hits = set()
    for conn in root.iter("connection"):
        for attr in ("filename", "directory"):
            value = conn.get(attr) or ""
            if re.match(r"^([A-Za-z]:[\\/]|/)", value):
                hits.add(value)
    return sorted(hits)
