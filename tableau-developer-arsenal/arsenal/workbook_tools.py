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


def check_workbook(path: str | Path) -> list[str]:
    """Find what stops Tableau loading a workbook, from errors Tableau has actually raised.

    Covers schema constructs older loaders reject, references to sheets, fields and
    parameters that don't exist ("invalid unordered_map<K, T> key"), action order,
    and the dynamic zone visibility graph. An empty list is not proof the workbook
    renders as intended; open it in Tableau to confirm.
    """
    root = _load_twb(Path(path))
    problems: list[str] = []
    text = ET.tostring(root, encoding="unicode")

    for el, why in [("computed-sort", "use <sort class='computed'>"),
                    ("clear-option", "drop it; keeping the value is the default")]:
        if root.find(f".//{el}") is not None:
            problems.append(f"<{el}> is rejected by older loaders: {why}")
    if root.find(".//encodings/label") is not None:
        problems.append("<label> is not an encoding: put label fields on <text>")
    if root.find(".//column[@param-domain-type='all']") is not None:
        problems.append("param-domain-type='all' is invalid: use 'any'")
    for ds in root.iter("datasource"):
        if ds.find("layout") is not None and ds.find("layout").get("dim-percentage") is None:
            problems.append(f"data source {ds.get('caption') or ds.get('name')}: <layout> without dim-percentage")

    sheets = {w.get("name") for w in root.iter("worksheet")}
    for z in root.iter("zone"):
        if z.get("name") and z.get("name") not in sheets:
            problems.append(f"dashboard zone shows missing sheet {z.get('name')!r}")

    for w in root.iter("worksheet"):
        instances = {ci.get("name") for ci in w.iter("column-instance")}
        for dep in w.iter("datasource-dependencies"):
            cols = {c.get("name") for c in dep.findall("column")}
            for ci in dep.findall("column-instance"):
                if ci.get("column") not in cols:
                    problems.append(f"sheet {w.get('name')!r}: {ci.get('name')} has no <column> for {ci.get('column')}")
        for ref in re.findall(r"\[federated\.[^\]]+\]\.(\[[a-z]+:[^\]]+:[a-z]k\])", ET.tostring(w, encoding="unicode")):
            if ref not in instances:
                problems.append(f"sheet {w.get('name')!r}: {ref} is used but not declared")

    params = {c.get("name") for ds in root.iter("datasource") if ds.get("name") == "Parameters" for c in ds.findall("column")}
    for used in sorted(set(re.findall(r"\[Parameters\]\.(\[Parameter \d+\])", text)) - params):
        problems.append(f"parameter {used} is used but not defined")
    for d in root.iter("dashboard"):
        declared = {c.get("name") for dep in d.findall("datasource-dependencies") if dep.get("datasource") == "Parameters"
                    for c in dep.findall("column")}
        for z in d.iter("zone"):
            if z.get("type-v2") == "paramctrl" and z.get("param", "").split(".")[-1] not in declared:
                problems.append(f"dashboard {d.get('name')!r}: parameter control {z.get('param')} not declared on the dashboard")

    actions = root.find("actions")
    if actions is not None:
        order = {"action": 0, "datasources": 1, "datasource-dependencies": 2, "edit-parameter-action": 3}
        tags = [order.get(c.tag, 9) for c in actions]
        if tags != sorted(tags):
            problems.append("<actions> must list action, datasources, datasource-dependencies, edit-parameter-action in that order")
        for a in actions:
            src = a.find("source")
            if src is not None and src.get("worksheet") not in sheets:
                problems.append(f"action {a.get('caption')!r} starts from missing sheet {src.get('worksheet')!r}")

    graph = root.find("datagraph/graph")
    if graph is not None:
        if graph.find("node-execution-subgraphs") is None:
            problems.append("datagraph needs <node-execution-subgraphs> before <nodes>")
        nodes = list(graph.find("nodes") if graph.find("nodes") is not None else [])
        node_ids = {n.get("node-guid") for n in nodes}
        paired = {p.get("node-guid") for p in graph.iter("pair")}
        if node_ids - paired:
            problems.append(f"datagraph: {len(node_ids - paired)} node(s) missing from node-execution-subgraphs")
        outputs = [e.get("from") for e in graph.iter("edge")]
        if len(outputs) != len(set(outputs)):
            problems.append("datagraph: each zone needs its own single-value-field-node (an output feeds several zones)")
        zone_ids = {z.get("id") for z in root.iter("zone")}
        dash_ids = {d.find("simple-id").get("uuid") for d in root.iter("dashboard") if d.find("simple-id") is not None}
        for n in nodes:
            if n.tag == "dashboard-zone-visibility-node":
                if n.get("zone-id") not in zone_ids:
                    problems.append(f"datagraph: zone {n.get('zone-id')} does not exist")
                if n.get("dashboard-identifier") not in dash_ids:
                    problems.append("datagraph: dashboard-identifier must be the dashboard's simple-id")
    return problems


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
