"""Build Tableau workbooks (.twbx) from Python, without Tableau Desktop.

The XML conventions here were checked against Tableau's own loader, error by error:
every rule in RULES.md under the skill folder maps to a construct below. Use
`workbook_tools.check_workbook` on the result before opening it in Tableau.

    wb = Workbook()
    year = wb.param("Hiring year", "2022", ["2022", "2021"])
    ds = wb.datasource("emp", "Employees", "employees.csv", [("hire_date", "date"), ("gender", "string")])
    share = ds.calc("Female %", "real", "AVG(IIF([gender] = 'Female', 1, 0))", fmt="p0.0%")
    wb.worksheet("Female share", ds, panes=[pane("Text", enc=[("text", F(ds, share))])])
    dash = wb.dashboard("Home", 1200, 800)
    dash.root = N("vert", kids=[sheet_zone("Female share")])
    wb.save("out.twbx", data_dir="data")
"""

from __future__ import annotations

import itertools
import re
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr as q

SANS = "Trebuchet MS"
SERIF = "Georgia"

# Features the workbook declares; Tableau validates the XML against them.
MANIFEST = ["BasicButtonObject", "CollapsiblePane", "DashboardExportButton", "DashboardExportButtonCrosstab",
            "DatagraphCoreV1", "DatagraphNodeDashboardZoneVisibilityV1", "DatagraphNodeSingleValueFieldV1",
            "ParameterAction", "SheetIdentifierTracking", "WindowsPersistSimpleIdentifiers", "ZoneVisibilityControl"]

_REMOTE_TYPES = {"string": 129, "integer": 20, "real": 5, "date": 133, "boolean": 11}
_DERIVATION = {"none": "None", "usr": "User", "sum": "Sum", "min": "Min", "max": "Max", "avg": "Avg", "tmn": "Month-Trunc"}


def _uid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def _guid() -> str:
    return str(uuid.uuid4())


# -- parameters ----------------------------------------------------------

class Param:
    """A string parameter. `members=None` accepts any typed value (search boxes)."""

    def __init__(self, index: int, caption: str, default: str, members: list[str] | None):
        self.name = f"[Parameter {index}]"
        self.ref = f"[Parameters].{self.name}"
        self.caption, self.default, self.members = caption, default, members

    def xml(self) -> str:
        val = f'"{self.default}"'
        if self.members is None:
            dom, mem = "param-domain-type='any'", ""  # 'all' is rejected by Tableau's schema
        else:
            dom = "param-domain-type='list'"
            mem = "<members>" + "".join(f"<member value={q(chr(34) + m + chr(34))} />" for m in self.members) + "</members>"
        return (f"<column caption={q(self.caption)} datatype='string' name={q(self.name)} {dom} role='measure' "
                f"type='nominal' value={q(val)}><calculation class='tableau' formula={q(val)} />{mem}</column>")


# -- data sources --------------------------------------------------------

class DataSource:
    """A CSV packaged inside the .twbx (Data/<folder>/<file>), plus its calculated fields."""

    def __init__(self, wb: "Workbook", key: str, caption: str, filename: str, columns: list[tuple[str, str]]):
        self.wb, self.caption, self.filename = wb, caption, filename
        self.name = f"federated.{key}"
        self.conn = f"textscan.{key}"
        self.cols = []
        for col, dt in columns:
            role = "measure" if dt in ("integer", "real") else "dimension"
            typ = "quantitative" if role == "measure" else ("ordinal" if dt == "date" else "nominal")
            self.cols.append((col, dt, role, typ))
        self.calcs: dict[str, dict] = {}
        self.palettes: list[tuple[str, list[tuple[str, str]]]] = []
        self._zero_one: tuple[str, str] | None = None

    def calc(self, caption: str, datatype: str, formula: str, *, role: str | None = None,
             typ: str | None = None, fmt: str | None = None) -> str:
        """Add a calculated field; returns its internal name for use in formulas and F()."""
        role = role or ("measure" if datatype in ("integer", "real") else "dimension")
        typ = typ or ("quantitative" if role == "measure" else "nominal")
        name = f"[Calculation_{next(self.wb._calc_ids)}]"
        self.calcs[name] = dict(caption=caption, datatype=datatype, role=role, type=typ, formula=formula, fmt=fmt)
        return name

    def ref(self, field: str) -> str:
        """Full reference to a field, as dynamic zone visibility needs it."""
        return f"[{self.name}].{field}"

    def palette(self, field: str, mapping: dict[str, str]) -> None:
        """Fixed colours for a discrete field's values, e.g. {'Current': '#cea25a'}."""
        self.palettes.append((f"[none:{field.strip('[]')}:nk]", list(mapping.items())))

    def zero_one(self) -> tuple[str, str]:
        """The 0 / 1 fields the deselect trick filters on (created once)."""
        if not self._zero_one:
            self._zero_one = (self.calc("Zero", "integer", "0", role="dimension", typ="ordinal"),
                              self.calc("One", "integer", "1", role="dimension", typ="ordinal"))
        return self._zero_one

    def column_xml(self, name: str) -> str:
        if name in self.calcs:
            c = self.calcs[name]
            fmt = f" default-format={q(c['fmt'])}" if c["fmt"] else ""
            return (f"<column caption={q(c['caption'])} datatype={q(c['datatype'])}{fmt} name={q(name)} role={q(c['role'])} "
                    f"type={q(c['type'])}><calculation class='tableau' formula={q(c['formula'])} /></column>")
        for col, dt, role, typ in self.cols:
            if f"[{col}]" == name:
                return f"<column datatype={q(dt)} name={q(name)} role={q(role)} type={q(typ)} />"
        raise KeyError(f"{name} is not a column or calculation of {self.caption}")

    def kind(self, field: str) -> tuple[str, str]:
        if field in self.calcs:
            return self.calcs[field]["role"], self.calcs[field]["type"]
        for col, _, role, typ in self.cols:
            if f"[{col}]" == field:
                return role, typ
        raise KeyError(field)

    def xml(self, folder: str) -> str:
        cols = "".join(f"<column datatype={q(dt)} name={q(c)} ordinal={q(str(i))} />" for i, (c, dt, _, _) in enumerate(self.cols))
        meta = "".join(
            f"<metadata-record class='column'><remote-name>{c}</remote-name><remote-type>{_REMOTE_TYPES[dt]}</remote-type>"
            f"<local-name>[{c}]</local-name><parent-name>[{self.filename}]</parent-name><remote-alias>{c}</remote-alias>"
            f"<ordinal>{i}</ordinal><local-type>{dt}</local-type>"
            f"<aggregation>{'Sum' if dt in ('integer', 'real') else 'Year' if dt == 'date' else 'Count'}</aggregation>"
            f"<contains-null>true</contains-null></metadata-record>" for i, (c, dt, _, _) in enumerate(self.cols))
        body = "".join(self.column_xml(f"[{c[0]}]") for c in self.cols) + "".join(self.column_xml(n) for n in self.calcs)
        # A palette only applies when its field is declared as a column-instance on the data source.
        body += "".join(f"<column-instance column={q('[' + inst.split(':')[1] + ']')} derivation='None' name={q(inst)} "
                        f"pivot='key' type='nominal' />" for inst, _ in self.palettes)
        style = ""
        if self.palettes:
            style = "<style><style-rule element='mark'>" + "".join(
                f"<encoding attr='color' field={q(inst)} type='palette'>" +
                "".join(f"<map to={q(color)}><bucket>{escape(chr(34) + value + chr(34))}</bucket></map>" for value, color in mapping) +
                "</encoding>" for inst, mapping in self.palettes) + "</style-rule></style>"
        table = "[" + self.filename.replace(".", "#") + "]"
        # No <layout> element: older loaders require attributes the newer one dropped, and it is optional.
        return (f"<datasource caption={q(self.caption)} inline='true' name={q(self.name)} version='18.1'><connection class='federated'>"
                f"<named-connections><named-connection caption={q(self.caption)} name={q(self.conn)}><connection class='textscan' "
                f"directory={q(folder)} filename={q(self.filename)} password='' server='' /></named-connection></named-connections>"
                f"<relation connection={q(self.conn)} name={q(self.filename)} table={q(table)} type='table'>"
                f"<columns character-set='UTF-8' header='yes' locale='en_US' separator=','>{cols}</columns></relation>"
                f"<metadata-records>{meta}</metadata-records></connection><aliases enabled='yes' />{body}{style}</datasource>")


class F:
    """A field placed in a view. prefix: none (dimension), usr (calc measure), sum/min/max/avg, tmn (month)."""

    def __init__(self, ds: DataSource, field: str, prefix: str | None = None, suffix: str | None = None):
        self.ds, self.field = ds, field
        role, typ = ds.kind(field)
        if prefix is None:
            prefix = "usr" if role == "measure" and field in ds.calcs else ("sum" if role == "measure" else "none")
        if suffix is None:
            suffix = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}[typ] if prefix in ("none", "usr") else "qk"
        self.prefix, self.suffix = prefix, suffix
        self.name = f"[{prefix}:{field.strip('[]')}:{suffix}]"
        self.ref = f"[{ds.name}].{self.name}"

    def xml(self) -> str:
        typ = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[self.suffix]
        return (f"<column-instance column={q(self.field)} derivation={q(_DERIVATION[self.prefix])} name={q(self.name)} "
                f"pivot='key' type={q(typ)} />")


def runs(parts: list) -> str:
    """Formatted text. Each part is '\\n' or (text | F | Param, {fontcolor, fontsize, bold, fontname})."""
    out = []
    for p in parts:
        if p == "\n":
            out.append("<run>Æ&#10;</run>")
            continue
        content, attrs = p
        a = {"fontname": SANS, **attrs}
        attr = "".join(f" {k}={q(str(v))}" for k, v in sorted(a.items()))
        if isinstance(content, (F, Param)):
            body = escape(f"<{content.ref}>")
        else:
            body = escape(content)
        out.append(f"<run{attr}>{body}</run>")
    return "<formatted-text>" + "".join(out) + "</formatted-text>"


def pane(mark: str, *, enc=(), label=None, tooltip=None, mark_fmt=None, cell="", extra_style="",
         axis: F | None = None, axis_attr: str = "x-axis-name", pane_id: int | None = None, fixed_size: bool = False) -> dict:
    """One marks card. enc: [(shelf, F | Param)], shelf in color/size/text/lod/tooltip/path/shape.

    Use 'text' for the Label shelf (there is no 'label' encoding). A Param shown in a
    label or tooltip must also be on the card, so pass it in enc too.
    """
    return dict(mark=mark, enc=list(enc), label=label, tooltip=tooltip, mark_fmt=mark_fmt or {}, cell=cell,
                extra_style=extra_style, axis=axis, axis_attr=axis_attr, id=pane_id, fixed_size=fixed_size)


QUIET_STYLE = (
    "<style-rule element='table'><format attr='background-color' value='#00000000' /><format attr='show-null-value-warning' value='false' /></style-rule>"
    "<style-rule element='gridline'><format attr='line-visibility' value='off' /><format attr='stroke-size' value='0' /></style-rule>"
    "<style-rule element='zeroline'><format attr='line-visibility' value='off' /><format attr='stroke-size' value='0' /></style-rule>"
    "<style-rule element='dropline'><format attr='line-visibility' value='off' /></style-rule>"
    "<style-rule element='table-div'><format attr='line-visibility' scope='cols' value='off' /><format attr='stroke-size' scope='cols' value='0' />"
    "<format attr='line-visibility' scope='rows' value='off' /><format attr='stroke-size' scope='rows' value='0' /></style-rule>"
    "<style-rule element='header'><format attr='band-color' scope='rows' value='#00000000' /><format attr='band-color' scope='cols' value='#00000000' /></style-rule>"
    "<style-rule element='worksheet'><format attr='display-field-labels' scope='rows' value='false' />"
    "<format attr='display-field-labels' scope='cols' value='false' /></style-rule>")


def fixed_axis(f: F, lo: float, hi: float, scope: str, *, sync: bool = False, show: bool = False) -> str:
    """Axis style: fixed range, hidden unless show=True. Put inside <style-rule element='axis'>."""
    s = " synchronized='true'" if sync else ""
    out = (f"<encoding attr='space' class='0' field={q(f.ref)} field-type='quantitative' fold='true' max={q(str(hi))} "
           f"min={q(str(lo))} range-type='fixed' scope={q(scope)}{s} type='space' />")
    if not show:
        out += f"<format attr='display' class='0' field={q(f.ref)} scope={q(scope)} value='false' />"
    return out


# -- dashboard layout ----------------------------------------------------

def N(kind: str | None = None, size: float | None = None, kids=(), show=None, bg=None, border=None, bw=1, pad=0, **attrs) -> dict:
    """Tiled layout node. kind 'vert'/'horz' for containers, None for leaves.

    size: fixed pixels along the parent's direction (None shares what is left; fix every
    height you can so Tableau does not redistribute space). show: (full field ref, visible
    at start) for dynamic zone visibility on a boolean calc.
    """
    return dict(kind=kind, size=size, kids=list(kids), show=show, bg=bg, border=border, bw=bw, pad=pad, attrs=attrs)


def blank_zone(size=None, **kw) -> dict:
    return N(size=size, type_v2="empty", **kw)


def text_zone(size, parts, **kw) -> dict:
    return N(size=size, type_v2="text", forceUpdate="true", inner=runs(parts), **kw)


def param_zone(size, param: Param, title: str, *, mode: str = "compact", title_color: str = "#757781", **kw) -> dict:
    return N(size=size, type_v2="paramctrl", mode=mode, param=param.ref, custom_title="true",
             inner=runs([(title, {"fontcolor": title_color, "fontsize": 9})]), **kw)


def sheet_zone(name: str, size=None, **kw) -> dict:
    return N(size=size, name=name, show_title="false", **kw)


def image_zone(path: str, size=None, **kw) -> dict:
    """A picture packaged in the .twbx; add the file with Workbook.image()."""
    return N(size=size, type_v2="bitmap", param=path, is_scaled="1", **kw)


def toggle_button(target: dict, first_image: str, second_image: str, size=None, **kw) -> dict:
    """Show/hide button for `target` (a node created with hidden_by_user='true' to start hidden).

    The images and state order follow a working Tableau workbook: state 1 (second image) while
    the target is hidden.
    """
    return N(size=size, type_v2="dashboard-object", button=("toggle", target, first_image, second_image), **kw)


def export_button(kind: str, image: str, size=None, **kw) -> dict:
    """Export the dashboard: kind 'pdf', 'powerpoint' or 'crosstab'."""
    return N(size=size, type_v2="dashboard-object", button=("export", kind, image), **kw)


class Dashboard:
    def __init__(self, wb: "Workbook", name: str, width: int, height: int, background: str = "#ffffff"):
        self.wb, self.name, self.width, self.height, self.background = wb, name, width, height, background
        self.id = _uid()
        self.window_id = _uid()  # toggle buttons address the dashboard's window
        self.root: dict | None = None
        self.floating: list[tuple[dict, tuple[float, float, float, float]]] = []
        self.zones_with_visibility: list[tuple[int, str]] = []

    def float(self, node: dict, x: float, y: float, w: float, h: float) -> dict:
        """Place a zone (or a container and its contents) at fixed pixels above the tiled layout.

        Floating zones are written as siblings of the tiled layout inside <zones>, as Tableau does;
        inside the tiled layout they get misplaced. Later floats draw on top of earlier ones.
        """
        self.floating.append((node, (x, y, w, h)))
        return node

    def _ids(self, node, ids):
        node["zid"] = next(ids)
        for k in node["kids"]:
            self._ids(k, ids)

    def _place(self, node, x, y, w, h):
        node["rect"] = (x, y, w, h)
        if not node["kind"]:
            return
        p = node["pad"]
        ix, iy, iw, ih = x + p, y + p, w - 2 * p, h - 2 * p
        horz = node["kind"] == "horz"
        live = [k for k in node["kids"] if not (k["show"] and not k["show"][1])]
        fixed = sum(k["size"] for k in live if k["size"] is not None)
        flex = [k for k in live if k["size"] is None]
        share = ((iw if horz else ih) - fixed) / len(flex) if flex else 0
        pos = ix if horz else iy
        for k in node["kids"]:
            length = k["size"] if k["size"] is not None else share
            self._place(k, *((pos, iy, length, ih) if horz else (ix, pos, iw, length)))
            if k in live:
                pos += length

    def _emit(self, node, parent_kind) -> str:
        zid = node["zid"]
        x, y, w, h = node["rect"]
        a = dict(x=round(x * 100000 / self.width), y=round(y * 100000 / self.height),
                 w=round(w * 100000 / self.width), h=round(h * 100000 / self.height))
        a.update(node["attrs"])
        if node["kind"]:
            a["type_v2"], a["param"] = "layout-flow", node["kind"]
        if node["size"] is not None and parent_kind:
            a["fixed_size"], a["is_fixed"] = str(round(node["size"])), "true"
        if node["show"]:
            field, visible = node["show"]
            self.zones_with_visibility.append((zid, field))
            if not visible:
                a["hidden_by_user"] = "true"
        inner = a.pop("inner", "")
        button = a.pop("button", None)
        if button and button[0] == "toggle":
            _, target, first, second = button
            hidden = bool(target["attrs"].get("hidden_by_user"))
            inner = (f"<button action='' active-visual-state-index='{1 if hidden else 0}'><toggle-action>"
                     + escape(f'tabdoc:toggle-button-click-action window-id="{self.window_id}" zone-id="{zid}" zone-ids=[{target["zid"]}]')
                     + f"</toggle-action><button-visual-state><image-path>{escape(first)}</image-path></button-visual-state>"
                     f"<button-visual-state><image-path>{escape(second)}</image-path></button-visual-state></button>")
        elif button:
            _, kind, image = button
            inner = (f"<button action='' button-click-action-metadata='{kind}'><export-button-action>"
                     + escape(f'tabdoc:abstract-dashboard-button-export-wrapper dashboard-button-export-type="{kind}" dashboarddoc-id="{self.id}"')
                     + f"</export-button-action><button-visual-state><image-path>{escape(image)}</image-path></button-visual-state></button>")
        if node["border"]:
            st = (f"<format attr='border-color' value='{node['border']}' /><format attr='border-style' value='solid' />"
                  f"<format attr='border-width' value='{node['bw']}' />")
        else:
            st = "<format attr='border-color' value='#000000' /><format attr='border-style' value='none' /><format attr='border-width' value='0' />"
        st += f"<format attr='margin' value='0' /><format attr='padding' value='{node['pad']}' />"
        if node["bg"]:
            st += f"<format attr='background-color' value='{node['bg']}' />"
        attrs = "".join(f" {k.replace('_', '-')}={q(str(v))}" for k, v in sorted(a.items()))
        kids = "".join(self._emit(k, node["kind"]) for k in node["kids"])
        return f"<zone id={q(str(zid))}{attrs}>{inner}{kids}<zone-style>{st}</zone-style></zone>"

    def sheets(self) -> list[str]:
        out = []
        def walk(n):
            if n["attrs"].get("name"):
                out.append(n["attrs"]["name"])
            for k in n["kids"]:
                walk(k)
        walk(self.root)
        for node, _ in self.floating:
            walk(node)
        return out

    def xml(self) -> str:
        self.zones_with_visibility = []
        ids = itertools.count(3)
        self._ids(self.root, ids)
        for node, _ in self.floating:
            self._ids(node, ids)
        self._place(self.root, 0, 0, self.width, self.height)
        zones = self._emit(self.root, None)
        floating = ""
        for node, rect in self.floating:
            self._place(node, *rect)
            floating += self._emit(node, None)
        params = "".join(p.xml() for p in self.wb.params)
        # Parameter controls look their parameter up here; without it Tableau stops with
        # "invalid unordered_map<K, T> key".
        deps = (f"<datasources><datasource name='Parameters' /></datasources><datasource-dependencies datasource='Parameters'>"
                f"{params}</datasource-dependencies>") if self.wb.params else ""
        return (f"<dashboard name={q(self.name)}><style><style-rule element='table'><format attr='background-color' value='{self.background}' /></style-rule>"
                f"<style-rule element='parameter-ctrl'><format attr='font-family' value='{self.wb.font}' /></style-rule></style>"
                f"<size maxheight='{self.height}' maxwidth='{self.width}' minheight='{self.height}' minwidth='{self.width}' />{deps}"
                f"<zones><zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>{zones}"
                f"<zone-style><format attr='background-color' value='{self.background}' /></zone-style></zone>{floating}</zones>"
                f"<simple-id uuid={q(self.id)} /></dashboard>")


# -- workbook ------------------------------------------------------------

class Workbook:
    def __init__(self, font: str = SANS, data_folder: str = "Data/datasources"):
        self.font, self.data_folder = font, data_folder
        self._calc_ids = itertools.count(9100000000000000001)
        self.params: list[Param] = []
        self.datasources: list[DataSource] = []
        self.sheets: list[tuple[str, str]] = []
        self.dashboards: list[Dashboard] = []
        self.images: dict[str, Path] = {}
        self._param_actions: list[tuple] = []
        self._deselects: list[tuple] = []

    def param(self, caption: str, default: str, members: list[str] | None = None) -> Param:
        p = Param(len(self.params) + 1, caption, default, members)
        self.params.append(p)
        return p

    def datasource(self, key: str, caption: str, filename: str, columns: list[tuple[str, str]]) -> DataSource:
        ds = DataSource(self, key, caption, filename, columns)
        self.datasources.append(ds)
        return ds

    def image(self, path_in_workbook: str, source: str | Path) -> str:
        """Package a picture (for image_zone or buttons); returns the path to use, e.g. 'Image/logo.png'."""
        self.images[path_in_workbook] = Path(source)
        return path_in_workbook

    def dashboard(self, name: str, width: int, height: int, background: str = "#ffffff") -> Dashboard:
        d = Dashboard(self, name, width, height, background)
        self.dashboards.append(d)
        return d

    def worksheet(self, name: str, ds: DataSource, *, rows=(), cols=(), panes=(), filters=(), sorts=(),
                  style: str = "", title=None, tooltip_none: bool = False, dual_cols=False, dual_rows=False) -> None:
        """filters: [(F, member)] keeps one value, e.g. (F(ds, flag), 'true'). sorts: [(F dimension, F measure)]."""
        fields = list(rows) + list(cols) + [f for f, _ in filters] + [x for s in sorts for x in s]
        params = set()
        for p in panes:
            fields += [f for _, f in p["enc"] if isinstance(f, F)]
            params.update(f.name for _, f in p["enc"] if isinstance(f, Param))
        inst: dict[str, F] = {}
        for f in fields:
            inst.setdefault(f.name, f)
        needed, used = self._deps(ds, [f.field for f in inst.values()])
        params |= used
        for t in [title] + [p["label"] for p in panes] + [p["tooltip"] for p in panes]:
            if t:
                params.update(re.findall(r"\[Parameters\]\.(\[Parameter \d+\])", t))
        pdeps = ("<datasource-dependencies datasource='Parameters'>" + "".join(p.xml() for p in self.params if p.name in params)
                 + "</datasource-dependencies>") if params else ""
        filt = "".join(f"<filter class='categorical' column={q(f.ref)}><groupfilter function='member' level={q(f.name)} "
                       f"member={q(m)} user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' /></filter>"
                       for f, m in filters)
        # Classic sort element; <computed-sort> needs a manifest flag older loaders lack.
        srt = "".join(f"<sort class='computed' column={q(a.ref)} direction='ASC' using={q(b.ref)} />" for a, b in sorts)
        slices = ("<slices>" + "".join(f"<column>{escape(f.ref)}</column>" for f, _ in filters) + "</slices>") if filters else ""
        pane_xml = ""
        for p in panes:
            pid = f" id={q(str(p['id']))} {p['axis_attr']}={q(p['axis'].ref)}" if p["id"] is not None else ""
            enc = "".join(f"<{k} column={q(f.ref)} />" for k, f in p["enc"])
            fmt = "".join(f"<format attr={q(k)} value={q(v)} />" for k, v in p["mark_fmt"].items())
            pane_xml += (f"<pane selection-relaxation-option='selection-relaxation-allow'{pid}><view><breakdown value='auto' /></view>"
                         f"<mark class={q(p['mark'])} />" + ("<mark-sizing mark-sizing-setting='marks-scaling-off' />" if p["fixed_size"] else "")
                         + (f"<encodings>{enc}</encodings>" if enc else "")
                         + (f"<customized-tooltip>{p['tooltip']}</customized-tooltip>" if p["tooltip"] else "")
                         + (f"<customized-label>{p['label']}</customized-label>" if p["label"] else "")
                         + f"<style>{p['cell']}<style-rule element='mark'>{fmt}</style-rule>{p['extra_style']}</style></pane>")

        def shelf(xs, dual):
            if not xs:
                return ""
            if dual:
                return "(" + " + ".join(x.ref for x in xs) + ")"
            out = xs[-1].ref
            for x in reversed(xs[:-1]):
                out = f"({x.ref} / {out})"
            return out

        ttl = f"<layout-options><title>{title}</title></layout-options>" if title else ""
        font = f"<style-rule element='worksheet'><format attr='font-family' value='{self.font}' /></style-rule>"
        xml = (f"<worksheet name={q(name)}>{ttl}<table><view><datasources><datasource caption={q(ds.caption)} name={q(ds.name)} />"
               + ("<datasource name='Parameters' />" if params else "") + f"</datasources>{pdeps}<datasource-dependencies datasource={q(ds.name)}>"
               + "".join(ds.column_xml(n) for n in sorted(needed)) + "".join(f.xml() for f in inst.values())
               + f"</datasource-dependencies>{filt}{srt}{slices}<aggregation value='true' /></view><style>{QUIET_STYLE}{font}{style}</style>"
               + f"<panes>{pane_xml}</panes><rows>{escape(shelf(list(rows), dual_rows))}</rows><cols>{escape(shelf(list(cols), dual_cols))}</cols>"
               + ("<tooltip-style tooltip-mode='none' />" if tooltip_none else "") + f"</table><simple-id uuid={q(_uid())} /></worksheet>")
        self.sheets.append((name, xml))

    @staticmethod
    def _deps(ds: DataSource, fields: list[str]) -> tuple[list[str], set[str]]:
        seen, stack, params = [], list(fields), set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.append(n)
            if n in ds.calcs:
                f = ds.calcs[n]["formula"]
                params.update(re.findall(r"\[Parameters\]\.(\[Parameter \d+\])", f))
                stack.extend(re.findall(r"\[[^\]]+\]", re.sub(r"\[Parameters\]\.\[Parameter \d+\]", "", f)))
        return seen, params

    # -- interactivity -----------------------------------------------------

    def set_param_on_click(self, dashboard: Dashboard, sheet: str, field: F, param: Param, caption: str) -> None:
        """Clicking a mark on `sheet` sets `param` to `field` (an attribute on the sheet)."""
        self._param_actions.append((dashboard, sheet, field, param, caption))

    def deselect_on_click(self, dashboard: Dashboard, sheet: str, ds: DataSource) -> None:
        """Clear the selection right after a click, so marks don't stay highlighted.

        Put both of ds.zero_one() on the sheet's lod.
        """
        ds.zero_one()
        self._deselects.append((dashboard, sheet, ds))

    def _actions_xml(self) -> str:
        n = itertools.count(1)
        name = lambda: q(f"[Action{next(n)}_{uuid.uuid4().hex.upper()}]")
        out = ""
        for dash, sheet, ds in self._deselects:
            zero, one = ds.zero_one()
            expr = f"tsl:{sheet}?%5B{ds.name}%5D.%5B{one.strip('[]')}%5D~s0=<[{ds.name}].[{zero.strip('[]')}]~na>"
            out += (f"<action caption={q('Deselect ' + sheet)} name={name()}><activation auto-clear='true' type='on-select' />"
                    f"<source dashboard={q(dash.name)} type='sheet' worksheet={q(sheet)} />"
                    f"<link caption={q('Deselect ' + sheet)} delimiter=',' escape='\\' expression={q(expr)} include-null='true' "
                    f"multi-select='true' url-escape='true' /><command command='tsc:tsl-filter'><param name='target' value={q(sheet)} /></command></action>")
        # Order matters: <action>s, then the data sources they use, then <edit-parameter-action>s.
        used = list(dict.fromkeys(ds for _, _, ds in self._deselects))
        if used:
            out += "<datasources>" + "".join(f"<datasource caption={q(d.caption)} name={q(d.name)} />" for d in used) + "</datasources>"
            out += "".join(f"<datasource-dependencies datasource={q(d.name)}>{d.column_xml(d.zero_one()[0])}{d.column_xml(d.zero_one()[1])}"
                           f"</datasource-dependencies>" for d in used)
        for dash, sheet, field, param, caption in self._param_actions:
            # No <clear-option>: older loaders reject it, and keeping the value is the default.
            out += (f"<edit-parameter-action caption={q(caption)} name={name()}><activation type='on-select' />"
                    f"<source dashboard={q(dash.name)} type='sheet' worksheet={q(sheet)} /><agg-type type='attr' />"
                    f"<params><param name='source-field' value={q(field.ref)} /><param name='target-parameter' value={q(param.ref)} /></params>"
                    f"</edit-parameter-action>")
        return out

    def _datagraph_xml(self) -> str:
        zones = [(d, zid, field) for d in self.dashboards for zid, field in d.zones_with_visibility]
        if not zones:
            return ""
        nodes, edges = [], []
        for dash, zid, field in zones:  # one field node per zone, as Tableau writes it
            out_guid, vin = _guid(), _guid()
            nodes.append(f"<single-value-field-node fieldname={q(field)} fieldname-input-guid={q(_guid())} node-guid={q(_guid())} "
                         f"value-output-guid={q(out_guid)} />")
            nodes.append(f"<dashboard-zone-visibility-node dashboard-identifier={q(dash.id)} node-guid={q(_guid())} "
                         f"visibility-input-guid={q(vin)} zone-id={q(str(zid))} />")
            edges.append(f"<edge from={q(out_guid)} to={q(vin)} />")
        sub = _guid()
        pairs = "".join(f"<pair execution-subgraph-guid={q(sub)} node-guid={q(g)} />"
                        for g in re.findall(r"node-guid=[\"']([^\"']+)[\"']", "".join(nodes)))
        return (f"<datagraph><graph><properties><default-execution-subgraph-guid value={q(sub)} /></properties>"
                f"<node-execution-subgraphs>{pairs}</node-execution-subgraphs><nodes>{''.join(nodes)}</nodes>"
                f"<edges>{''.join(edges)}</edges><pin-values /></graph></datagraph>")

    def to_xml(self) -> str:
        dashboards = "".join(d.xml() for d in self.dashboards)  # first: fills each dashboard's visibility zones
        names = [n for n, _ in self.sheets]
        on_dash = {s for d in self.dashboards for s in d.sheets()}
        windows = "".join(
            f"<window class='dashboard' maximized='true' name={q(d.name)}><viewpoints>"
            + "".join(f"<viewpoint name={q(s)}><zoom type='entire-view' /></viewpoint>" for s in d.sheets())
            + f"</viewpoints><active id='-1' /><simple-id uuid={q(d.window_id)} /></window>" for d in self.dashboards)
        windows += "".join(
            f"<window class='worksheet'{' hidden=' + chr(39) + 'true' + chr(39) if n in on_dash else ''} name={q(n)}><cards>"
            "<edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>"
            "<edge name='top'><strip size='2147483647'><card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip>"
            f"<strip size='31'><card type='title' /></strip></edge></cards><simple-id uuid={q(_uid())} /></window>" for n in names)
        params = ("<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'><aliases enabled='yes' />"
                  + "".join(p.xml() for p in self.params) + "</datasource>") if self.params else ""
        actions = self._actions_xml()
        return (f"<?xml version='1.0' encoding='utf-8' ?>\n<workbook original-version='18.1' source-build='2023.1.0 (20231.23.0505.1444)' "
                f"source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>"
                f"<document-format-change-manifest>{''.join(f'<{m} />' for m in MANIFEST)}</document-format-change-manifest><preferences />"
                f"<style><style-rule element='all'><format attr='font-family' value='{self.font}' /></style-rule></style>"
                f"<datasources>{params}{''.join(d.xml(self.data_folder) for d in self.datasources)}</datasources>"
                + (f"<actions>{actions}</actions>" if actions else "")
                + f"<worksheets>{''.join(x for _, x in self.sheets)}</worksheets>"
                + (f"<dashboards>{dashboards}</dashboards>" if dashboards else "")
                + f"<windows source-height='30'>{windows}</windows>{self._datagraph_xml()}</workbook>\n")

    def save(self, dest: str | Path, data_dir: str | Path, twb_name: str | None = None) -> Path:
        """Write the .twbx with each data source's CSV from data_dir packaged beside the workbook."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(twb_name or dest.with_suffix(".twb").name, self.to_xml())
            for ds in self.datasources:
                zf.write(Path(data_dir) / ds.filename, f"{self.data_folder}/{ds.filename}")
            for inside, source in self.images.items():
                zf.write(source, inside)
        return dest
