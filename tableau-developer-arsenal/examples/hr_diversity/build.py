"""Diversity in Human Resources: the Claude dashboard rebuilt as a Tableau workbook.

Structure from the Claude dashboard; title block, controls, icons, side panel and finish
from the original Tableau Public workbook (#RWFD); colours from the Claude dashboard.

    python examples/hr_diversity/prep_data.py examples/hr_diversity/data/hr_employees.csv out/hr_data
    copy examples\\hr_diversity\\data\\hr_employees.csv out\\hr_data\\   (the employee rows are a data source too)
    python examples/hr_diversity/build.py out/hr_data out/Diversity_in_HR.twbx
    tda twb check out/Diversity_in_HR.twbx

Rules this follows (see the skill's RULES.md): every field on a Marks card is numeric or plain
data text, never text made from a parameter; words that depend on a value come from number
formats; content floats above a plain tiled background, as the original does.
"""

from __future__ import annotations

import sys
from pathlib import Path

from arsenal.dashboard_builder import (SERIF, F, N, Workbook, blank_zone, export_button, fixed_axis, image_zone, pane,
                                       param_zone, runs, sheet_zone, text_zone, toggle_button)

DATA_DIR, OUT = sys.argv[1], sys.argv[2]
IMAGES = Path(__file__).parent / "images"

# Claude dashboard palette
PAGE, CARD, BORDER = "#f9f9f7", "#ffffff", "#e6e4df"
INK, MUTED, FAINT = "#1f1e1c", "#898781", "#b4b2ab"
ACCENT, TRACK, LAST_YEAR = "#2a78d6", "#efeeea", "#d9dde3"
UP, DOWN, CHIP = "#006300", "#8e2626", "#f3f2ee"
SANS = "Trebuchet MS"

wb = Workbook(font=SANS, data_folder="Data/hr-dashboard")
img = {name: wb.image(f"Image/{name}.png", IMAGES / f"{name}.png") for name in [
    "switch-on", "switch-off", "rwfd-logo", "export-pdf", "export-ppt", "export-xlsx",
    "view-overview-on", "view-overview-off", "view-table-on", "view-table-off"]}

year = wb.param("Hiring year", "2022", ["2022", "2021", "2020", "2019", "2018"])
measure = wb.param("Measure", "Diversity", ["Diversity", "Persons of color", "Female", "Male & NA"])
role_by = wb.param("Group roles by", "Position", ["Position", "Department", "Job role"])
bg_by = wb.param("Group background by", "Education", ["Education", "Education field", "Race", "Marital status"])
perf_by = wb.param("Group performance by", "Performance rating", ["Performance rating", "Employee satisfaction"])
search = wb.param("Search", "")
view = wb.param("View", "Overview", ["Overview", "Employee list"])
sort = wb.param("Sort", "Hire date")
YEAR_N = f"INT({year.ref})"

emp = wb.datasource("0hrclaudeemp001", "HR Employees", "hr_employees.csv", [
    ("employee_id", "string"), ("hire_date", "date"), ("gender", "string"), ("poc", "string"), ("race", "string"),
    ("diverse", "string"), ("position", "string"), ("department", "string"), ("job_role", "string"),
    ("performance", "string"), ("satisfaction", "integer"), ("education", "string"), ("education_field", "string"),
    ("marital_status", "string")])
trd = wb.datasource("0hrclaudetrd002", "Monthly shares", "trend.csv", [
    ("sel_year", "string"), ("metric", "string"), ("month_num", "integer"), ("month", "string"),
    ("this_year", "real"), ("year_before", "real"), ("hires", "integer"), ("hires_year_before", "integer")])
tbl = wb.datasource("0hrclaudetbl001", "Employee table", "employee_table.csv", [
    ("employee_id", "string"), ("hire_year", "integer"), ("column_name", "string"), ("col_order", "integer"),
    ("value", "string"), ("value_rank", "integer")])
vw = wb.datasource("0hrclaudevw0002", "Views", "views.csv", [("view", "string"), ("view_order", "integer"), ("view_label", "string")])

# -- calculations ----------------------------------------------------------

METRICS = [  # key, title, definition, row test, change coloured by direction
    ("Diversity", "Diversity", "Female or a person of color", "[diverse] = 'Diverse'", True),
    ("POC", "Persons of color", "Any race other than White", "[poc] = 'POC'", True),
    ("Female", "Female", "Gender recorded as female", "[gender] = 'Female'", True),
    ("MaleNA", "Male & NA", "Male or gender not recorded", "[gender] = 'Male & NA'", False),
]
period = emp.calc("Period", "string", f"IF YEAR([hire_date]) = {YEAR_N} THEN 'Current'\nELSEIF YEAR([hire_date]) = {YEAR_N} - 1 THEN 'Previous'\nEND")
cy_hires = emp.calc("Hires this year", "integer", f"SUM(IF {period} = 'Current' THEN 1 ELSE 0 END)", fmt="n#,##0")
year_num = emp.calc("Year", "integer", f"MIN({YEAR_N})", fmt="*0")
prev_year_num = emp.calc("Year before", "integer", f"MIN({YEAR_N} - 1)", fmt="*0")
EM = {}
for key, title, _, cond, _ in METRICS:
    m = {}
    m["cy"] = emp.calc(f"{title} % this year", "real", f"SUM(IF {period} = 'Current' AND {cond} THEN 1 ELSE 0 END)\n"
                       f"/ SUM(IF {period} = 'Current' THEN 1 ELSE 0 END)", fmt="p0.0%")
    m["py"] = emp.calc(f"{title} % year before", "real", f"SUM(IF {period} = 'Previous' AND {cond} THEN 1 ELSE 0 END)\n"
                       f"/ SUM(IF {period} = 'Previous' THEN 1 ELSE 0 END)", fmt="p0.0%")
    # Relative change, as the original shows it; the arrow comes from the number format.
    m["up"] = emp.calc(f"{title} change up", "real", f"IIF({m['cy']} >= {m['py']}, {m['cy']} / {m['py']} - 1, NULL)", fmt="*▲ 0.0%")
    m["down"] = emp.calc(f"{title} change down", "real", f"IIF({m['cy']} < {m['py']}, {m['cy']} / {m['py']} - 1, NULL)", fmt="*▼ 0.0%;▼ 0.0%")
    m["key"] = emp.calc(f"{title} measure key", "string", f"'{title}'")
    m["sel"] = emp.calc(f"Show {title} as selected", "boolean", f"{view.ref} = 'Overview' AND {measure.ref} = '{title}'")
    m["unsel"] = emp.calc(f"Show {title} as not selected", "boolean", f"{view.ref} = 'Overview' AND {measure.ref} <> '{title}'")
    EM[key] = m
dv = EM["Diversity"]
pts = f"({dv['cy']} - {dv['py']}) * 100"
d_up = emp.calc("Diversity points up", "real", f"IIF({pts} >= 0, {pts}, NULL)", fmt='*"up "0.0" pts"')
d_down = emp.calc("Diversity points down", "real", f"IIF({pts} < 0, {pts}, NULL)", fmt='*"down "0.0" pts";"down "0.0" pts"')
show_overview = emp.calc("Show overview", "boolean", f"{view.ref} = 'Overview'")
show_table = emp.calc("Show employee list", "boolean", f"{view.ref} = 'Employee list'")
track = emp.calc("Track", "real", "MIN(1.0)")


def by_measure(part):
    return f"CASE {measure.ref}\n" + "\n".join(f"WHEN '{t}' THEN {EM[k][part]}" for k, t, *_ in METRICS) + "\nEND"


in_window = emp.calc("In comparison window", "boolean", f"NOT ISNULL({period})")
cy_sel = emp.calc("Chosen measure this year", "real", by_measure("cy"), fmt="p0.0%")
py_sel = emp.calc("Chosen measure year before", "real", by_measure("py"), fmt="p0.0%")
picked = f"CASE {measure.ref}\n" + "\n".join(f"WHEN '{t}' THEN IIF({c}, 1, 0)" for _, t, _, c, _ in METRICS) + "\nEND"
cy_count = emp.calc("People counted this year", "integer", f"SUM(IF {period} = 'Current' THEN {picked} ELSE 0 END)", fmt="n#,##0")
satisfaction = emp.calc("Satisfaction label", "string",
                        "CASE [satisfaction]\nWHEN 1 THEN 'Very unsatisfied'\nWHEN 2 THEN 'Unsatisfied'\nWHEN 3 THEN 'Neutral'\n"
                        "WHEN 4 THEN 'Satisfied'\nELSE 'Very satisfied'\nEND")
ORDERS = {
    "Position": ["Vice President", "Director", "Manager", "Senior Professional", "Mid-level Professional", "Entry Level Professional"],
    "Education": ["Doctoral Degree", "Master's Degree", "Bachelor's Degree", "Associates Degree", "High School"],
    "Performance rating": ["Exceeds", "Fully Meets", "Needs Improvement", "PIP"],
    "Employee satisfaction": ["Very satisfied", "Satisfied", "Neutral", "Unsatisfied", "Very unsatisfied"],
}
GROUPINGS = {  # card: (picker, [(picker value, field)])
    "Role": (role_by, [("Position", "[position]"), ("Department", "[department]"), ("Job role", "[job_role]")]),
    "Background": (bg_by, [("Education", "[education]"), ("Education field", "[education_field]"), ("Race", "[race]"),
                           ("Marital status", "[marital_status]")]),
    "Performance": (perf_by, [("Performance rating", "[performance]"), ("Employee satisfaction", satisfaction)]),
}
lit = lambda v: f'"{v}"' if "'" in v else f"'{v}'"  # Master's Degree goes in double quotes
GROUPS = {}
for card_key, (picker, options) in GROUPINGS.items():
    group = emp.calc(f"{card_key} group", "string", f"CASE {picker.ref}\n" + "\n".join(f"WHEN '{v}' THEN {f}" for v, f in options) + "\nEND")
    hires = emp.calc(f"{card_key} group hires", "integer", f"{{FIXED {group} : SUM(IIF(YEAR([hire_date]) = {YEAR_N}, 1, 0))}}")
    hired = emp.calc(f"{card_key} group hired this year", "boolean", f"{hires} > 0")
    ranked = [(v, f) for v, f in options if v in ORDERS]
    listed = "".join(f"\nWHEN '{v}' THEN CASE {f}" + "".join(f" WHEN {lit(x)} THEN {i}" for i, x in enumerate(ORDERS[v], 1)) + " ELSE 90 END"
                     for v, f in ranked)
    is_ranked = " OR ".join(f"{picker.ref} = '{v}'" for v, _ in ranked) or "FALSE"
    # Ranked fields keep their listed order; others go largest share first; "Not recorded" last.
    sort_key = emp.calc(f"{card_key} sort", "real", f"MIN(IIF({group} = 'Not recorded', 1000, 0))\n"
                                                    f"+ MIN(CASE {picker.ref}{listed}\nELSE 0 END)\n+ IIF({is_ranked}, 0, -{cy_sel})")
    GROUPS[card_key] = dict(group=group, hired=hired, sort=sort_key, picker=picker)

trend_year = trd.calc("Chosen year rows", "boolean", f"[sel_year] = {year.ref}")

t_year = tbl.calc("Hired in chosen year", "boolean", f"[hire_year] = {YEAR_N}")
t_search = tbl.calc("Matches search", "boolean",
                    f"{search.ref} = '' OR {{FIXED [employee_id] : MAX(IIF(CONTAINS(LOWER([value]), LOWER({search.ref})), 1, 0))}} = 1")
t_head = tbl.calc("Column heading", "string", f"[column_name] + IIF([column_name] = {sort.ref}, '  ▲', '')")
t_sortval = tbl.calc("Row sort value", "integer", f"IIF([column_name] = {sort.ref}, [value_rank], NULL)")
t_people = tbl.calc("People shown", "integer", "COUNTD([employee_id])", fmt="n#,##0")

v_on = vw.calc("Is current view", "string", f"IIF([view] = {view.ref}, 'on', 'off')")
vw.palette(v_on, {"on": INK, "off": MUTED})

# -- worksheets ------------------------------------------------------------

CENTER = "<style-rule element='cell'><format attr='text-align' value='center' /><format attr='vertical-align' value='center' /></style-rule>"
LEFT = "<style-rule element='cell'><format attr='text-align' value='left' /><format attr='vertical-align' value='center' /></style-rule>"
RIGHT = "<style-rule element='cell'><format attr='text-align' value='right' /><format attr='vertical-align' value='center' /></style-rule>"
zero, one = emp.zero_one()
yr, pyr = F(emp, year_num), F(emp, prev_year_num)

mut, bold = {"fontcolor": MUTED, "fontsize": 11}, {"fontcolor": INK, "fontsize": 11, "bold": "true"}
cyn, dcy, dup, ddn = F(emp, cy_hires), F(emp, dv["cy"]), F(emp, d_up), F(emp, d_down)
wb.worksheet("Summary", emp, tooltip_none=True, panes=[pane(
    "Text", cell=LEFT, mark_fmt={"mark-labels-show": "true"},
    enc=[("text", cyn), ("text", yr), ("text", dcy), ("text", dup), ("text", ddn), ("text", pyr)],
    label=runs([("Of the ", mut), (cyn, bold), (" people hired in ", mut), (yr, bold), (", ", mut), (dcy, bold),
                (" were diverse (female or a person of color), ", mut), (dup, bold), (ddn, bold), (" on the ", mut),
                (pyr, bold), (" hiring class.", mut)]))])

for key, title, _, _, coloured in METRICS:
    m = EM[key]
    cy, up, dn = F(emp, m["cy"]), F(emp, m["up"]), F(emp, m["down"])
    wb.worksheet(f"KPI_{key}", emp, tooltip_none=True, panes=[pane(
        "Text", cell=CENTER, mark_fmt={"mark-labels-show": "true"},
        enc=[("lod", F(emp, m["key"])), ("lod", F(emp, zero)), ("lod", F(emp, one)), ("text", cy), ("text", yr)],
        label=runs([(cy, {"fontcolor": INK, "fontsize": 30, "fontname": SERIF}), "\n",
                    (yr, {"fontcolor": MUTED, "fontsize": 9}), (" hires", {"fontcolor": MUTED, "fontsize": 9})]))])
    # The original's change chip: a tinted square with the change, coloured by direction.
    up_c, dn_c = (UP, DOWN) if coloured else (MUTED, MUTED)
    wb.worksheet(f"Chip_{key}", emp, tooltip_none=True, panes=[pane(
        "Square", cell=CENTER, enc=[("text", up), ("text", dn)],
        mark_fmt={"mark-labels-show": "true", "mark-color": CHIP, "size": "14.5"},
        label=runs([(up, {"fontcolor": up_c, "fontsize": 10, "bold": "true"}), (dn, {"fontcolor": dn_c, "fontsize": 10, "bold": "true"})]))])
    # The original's progress bar under each card title: this year's share on a grey track.
    trk, val = F(emp, track), F(emp, m["cy"])
    wb.worksheet(f"Bar_{key}", emp, cols=[trk, val], dual_cols=True, tooltip_none=True,
                 panes=[pane("Bar"),
                        pane("Bar", pane_id=1, axis=trk, mark_fmt={"mark-color": TRACK, "size": "2", "has-stroke": "false"}),
                        pane("Bar", pane_id=2, axis=val, mark_fmt={"mark-color": ACCENT, "size": "2", "has-stroke": "false"})],
                 style="<style-rule element='axis'>" + fixed_axis(trk, 0, 1.0, "cols") + fixed_axis(val, 0, 1.0, "cols", sync=True) + "</style-rule>")

for key, title, *_ in METRICS:
    month, mnum = F(trd, "[month]"), F(trd, "[month_num]", "min")
    now, before = F(trd, "[this_year]", "sum"), F(trd, "[year_before]", "sum")
    wb.worksheet(f"Trend_{key}", trd, cols=[month], rows=[before, now], dual_rows=True, sorts=[(month, mnum)],
                 filters=[(F(trd, trend_year), "true"), (F(trd, "[metric]"), f'"{title}"')],
                 panes=[pane("Bar"),
                        pane("Bar", pane_id=1, axis=before, axis_attr="y-axis-name",
                             mark_fmt={"mark-color": LAST_YEAR, "size": "1.4", "has-stroke": "false"}),
                        pane("Bar", pane_id=2, axis=now, axis_attr="y-axis-name",
                             mark_fmt={"mark-color": ACCENT, "size": "0.6", "has-stroke": "false"})],
                 style="<style-rule element='axis'>" + fixed_axis(before, 0, 1.0, "rows") + fixed_axis(now, 0, 1.0, "rows", sync=True) + "</style-rule>"
                       + f"<style-rule element='label'><format attr='font-size' field='{month.ref}' value='7' />"
                       + f"<format attr='color' field='{month.ref}' value='{MUTED}' /></style-rule>")

for card_key in GROUPINGS:
    g = GROUPS[card_key]
    row, order = F(emp, g["group"]), F(emp, g["sort"])
    trk, cy, py, cnt, n = F(emp, track), F(emp, cy_sel), F(emp, py_sel), F(emp, cy_count), F(emp, cy_hires)
    tips = [("tooltip", cnt), ("tooltip", py), ("tooltip", n)]
    tip = runs([(row, {"fontcolor": MUTED, "fontsize": 9}), "\n", ("This year: ", {"fontcolor": INK, "fontsize": 10}),
                (cy, {"fontcolor": INK, "fontsize": 10, "bold": "true"}), "\n", (cnt, {"fontcolor": MUTED, "fontsize": 9}),
                (" of ", {"fontcolor": MUTED, "fontsize": 9}), (n, {"fontcolor": MUTED, "fontsize": 9}), (" hires", {"fontcolor": MUTED, "fontsize": 9}),
                "\n", ("Year before: ", {"fontcolor": MUTED, "fontsize": 9}), (py, {"fontcolor": MUTED, "fontsize": 9})])
    # Value on the right of the track, as the original's "60% | 80", with the year before.
    value = runs([(cy, {"fontcolor": INK, "fontsize": 9, "bold": "true"}), ("  |  ", {"fontcolor": FAINT, "fontsize": 9}),
                  (n, {"fontcolor": INK, "fontsize": 9, "bold": "true"}), ("   vs ", {"fontcolor": MUTED, "fontsize": 8}),
                  (py, {"fontcolor": MUTED, "fontsize": 8})])
    wb.worksheet(f"By_{card_key}", emp, rows=[row], cols=[trk, cy], dual_cols=True, sorts=[(row, order)],
                 filters=[(F(emp, in_window), "true"), (F(emp, g["hired"]), "true")],
                 panes=[pane("Bar", enc=tips, tooltip=tip),
                        pane("Bar", enc=tips + [("text", cy), ("text", n), ("text", py)], tooltip=tip, pane_id=1, axis=trk,
                             label=value, cell=RIGHT,
                             mark_fmt={"mark-color": TRACK, "size": "1.65", "has-stroke": "false", "mark-labels-show": "true", "mark-labels-cull": "false"}),
                        pane("Bar", enc=tips, tooltip=tip, pane_id=2, axis=cy,
                             mark_fmt={"mark-color": ACCENT, "size": "1.65", "has-stroke": "false"})],
                 style="<style-rule element='axis'>" + fixed_axis(trk, 0, 1.0, "cols") + fixed_axis(cy, 0, 1.0, "cols", sync=True) + "</style-rule>"
                       + f"<style-rule element='header'><format attr='width' field='{row.ref}' value='150' /></style-rule>"
                       + f"<style-rule element='label'><format attr='font-size' field='{row.ref}' value='10' />"
                       + f"<format attr='color' field='{row.ref}' value='{INK}' /></style-rule>")

vv, vo, vl = F(vw, "[view]"), F(vw, "[view_order]", "min"), F(vw, "[view_label]")
vz, v1 = vw.zero_one()
wb.worksheet("View_Toggle", vw, rows=[vv], sorts=[(vv, vo)], tooltip_none=True,
             panes=[pane("Text", enc=[("text", vl), ("color", F(vw, v_on)), ("lod", F(vw, vz)), ("lod", F(vw, v1))],
                         mark_fmt={"mark-labels-show": "true"}, label=runs([(vl, {"fontsize": 10})]), cell=RIGHT)],
             style=f"<style-rule element='header'><format attr='width' field='{vv.ref}' value='1' /></style-rule>"
                   f"<style-rule element='label'><format attr='color' field='{vv.ref}' value='#00000000' /><format attr='font-size' field='{vv.ref}' value='1' /></style-rule>")

tz, t1 = tbl.zero_one()
emp_id, head, value_f = F(tbl, "[employee_id]"), F(tbl, t_head), F(tbl, "[value]")
tfilters = [(F(tbl, t_year), "true"), (F(tbl, t_search), "true")]
wb.worksheet("Employee_Table", tbl, rows=[emp_id], cols=[head], filters=tfilters, tooltip_none=True,
             sorts=[(emp_id, F(tbl, t_sortval, "min")), (head, F(tbl, "[col_order]", "min"))],
             panes=[pane("Text", enc=[("text", value_f), ("lod", F(tbl, "[column_name]")), ("lod", F(tbl, tz)), ("lod", F(tbl, t1))],
                         mark_fmt={"mark-labels-show": "true"}, label=runs([(value_f, {"fontcolor": INK, "fontsize": 9})]), cell=LEFT)],
             style=f"<style-rule element='header'><format attr='width' field='{emp_id.ref}' value='1' /><format attr='height-header' value='30' />"
                   f"<format attr='band-color' scope='rows' value='{PAGE}' /></style-rule>"
                   f"<style-rule element='label'><format attr='color' field='{emp_id.ref}' value='#00000000' /><format attr='font-size' field='{head.ref}' value='9' />"
                   f"<format attr='color' field='{head.ref}' value='{INK}' /><format attr='font-weight' field='{head.ref}' value='bold' /></style-rule>")
ppl = F(tbl, t_people)
wb.worksheet("Employee_Count", tbl, filters=tfilters, tooltip_none=True,
             panes=[pane("Text", enc=[("text", ppl)], cell=LEFT, mark_fmt={"mark-labels-show": "true"},
                         label=runs([(ppl, {"fontcolor": INK, "fontsize": 9, "bold": "true"}),
                                     (" people shown. Select a column heading to sort by it.", {"fontcolor": MUTED, "fontsize": 9})]))])

# -- dashboard ---------------------------------------------------------------

W, H = 1300, 1100
home = wb.dashboard("Home", W, H, background=PAGE)
home.root = blank_zone(bg=PAGE)  # plain page; everything else floats above it, as in the original
t = lambda text, size, color=INK, **kw: (text, {"fontcolor": color, "fontsize": size, **kw})
OV, TB = (emp.ref(show_overview), True), (emp.ref(show_table), False)


def card(kids, pad=14, **kw):
    return N("vert", None, bg=CARD, border=BORDER, pad=pad, kids=kids, **kw)


def spaced(items, gap):
    out = []
    for i, item in enumerate(items):
        if i:
            out.append(blank_zone(gap))
        out.append(item)
    return out


# Title block (original layout)
home.float(text_zone(None, [t("Diversity in", 12, MUTED), "\n", t("HUMAN RESOURCES", 28, INK)]), 30, 22, 520, 78)
home.float(sheet_zone("Summary"), 32, 102, 780, 30)

# View switch with the original's icons: dark icon for the view showing, grey for the other
home.float(sheet_zone("View_Toggle"), 846, 26, 128, 70)
home.float(image_zone(img["view-overview-on"], show=OV), 980, 30, 26, 26)
home.float(image_zone(img["view-overview-off"], show=TB), 980, 30, 26, 26)
home.float(image_zone(img["view-table-on"], show=TB), 980, 64, 26, 26)
home.float(image_zone(img["view-table-off"], show=OV), 980, 64, 26, 26)

# Filters and Legends switches, each showing a small panel below them (hidden until switched on)
filter_panel = N("vert", None, bg=CARD, border=BORDER, pad=6, hidden_by_user="true", kids=[param_zone(None, year, "Hiring year")])
legend_panel = N("vert", None, bg=CARD, border=BORDER, pad=8, hidden_by_user="true", kids=[text_zone(None, [
    t("▲ Increase", 9, UP, bold="true"), t("    ", 9), t("▼ Decrease", 9, DOWN, bold="true"), "\n",
    t("■ ", 9, ACCENT), t("Chosen year", 9, MUTED), t("    ", 9), t("■ ", 9, LAST_YEAR), t("Year before", 9, MUTED)])])
home.float(text_zone(None, [t("Filters ⚙", 10, MUTED)]), 1040, 26, 90, 24)
home.float(toggle_button(filter_panel, img["switch-on"], img["switch-off"]), 1044, 54, 50, 28)
home.float(text_zone(None, [t("Legends", 10, MUTED)]), 1150, 26, 90, 24)
home.float(toggle_button(legend_panel, img["switch-on"], img["switch-off"]), 1154, 54, 50, 28)

# Side panel (original): logo, export buttons, credit
home.float(card([
    image_zone(img["rwfd-logo"], 64), text_zone(22, [t("#RWFD Solutions", 7, MUTED)]), blank_zone(1, bg=BORDER),
    blank_zone(), text_zone(20, [t("EXPORT", 7, MUTED)]), blank_zone(8),
    export_button("pdf", img["export-pdf"], 30), blank_zone(12), export_button("powerpoint", img["export-ppt"], 30),
    blank_zone(12), export_button("crosstab", img["export-xlsx"], 30), blank_zone(24), blank_zone(1, bg=BORDER),
    text_zone(40, [t("DESIGN:", 7, MUTED), "\n", t("ABHINAV KR", 7, MUTED)]),
], pad=10), 1196, 160, 80, 916)


def kpi_card(key, title, definition):
    m = EM[key]
    return card([
        blank_zone(3, bg=ACCENT, show=(emp.ref(m["sel"]), key == "Diversity")),
        blank_zone(3, bg=CARD, show=(emp.ref(m["unsel"]), key != "Diversity")),
        blank_zone(6),
        text_zone(22, [t(title.upper(), 12, INK, bold="true")]),
        text_zone(16, [t(definition, 8, MUTED)]),
        sheet_zone(f"Bar_{key}", 12),
        blank_zone(4),
        sheet_zone(f"KPI_{key}", 62),
        N("horz", 26, kids=[blank_zone(), sheet_zone(f"Chip_{key}", 110), blank_zone()]),
        text_zone(18, [t("vs the year before", 8, MUTED)]),
        blank_zone(6),
        text_zone(18, [t("Monthly share   ", 8, MUTED), t("■ ", 8, ACCENT), (year, {"fontcolor": MUTED, "fontsize": 8}),
                       t("   ■ ", 8, LAST_YEAR), t("year before", 8, MUTED)]),
        sheet_zone(f"Trend_{key}"),
    ])


def breakdown_card(card_key, word):
    g = GROUPS[card_key]
    return card([
        text_zone(24, [(measure, {"fontcolor": INK, "fontsize": 11, "bold": "true"}), t(f" by {word}", 11, INK, bold="true")]),
        N("horz", 40, kids=[
            text_zone(None, [t("Shows the distribution of ", 8, MUTED), (measure, {"fontcolor": MUTED, "fontsize": 8}),
                             t(" across groups, this year against the year before.", 8, MUTED)]),
            text_zone(48, [t("View by:", 8, MUTED)]),
            param_zone(124, g["picker"], ""),
        ]),
        blank_zone(6),
        sheet_zone(f"By_{card_key}"),
    ])


CW = 1160 - 24
overview = N("vert", None, show=OV, kids=[
    N("horz", 330, kids=spaced([kpi_card(k, title, d) for k, title, d, *_ in METRICS], 14)),
    text_zone(34, [t("Each card shows the share of that year's hires and the change from the year before. "
                     "The bars compare each month with the same month a year earlier. Click a card to show it in the charts below.", 8, MUTED)]),
    N("horz", None, kids=spaced([breakdown_card("Role", "role"), breakdown_card("Background", "background"),
                                 breakdown_card("Performance", "performance")], 14)),
    text_zone(30, [t('"Not recorded" groups people whose department, job role, education or marital status is blank in the source data. '
                     "Hiring years 2018 to 2022 are offered because each has a full year before it. Data: Real World Fake Data (#RWFD).", 7, MUTED)]),
])
home.float(overview, 24, 160, CW, 916)
home.float(N("vert", None, show=TB, kids=[card([
    N("horz", 48, kids=[text_zone(None, [t("People hired in ", 13, INK, bold="true"), (year, {"fontcolor": INK, "fontsize": 13, "bold": "true"})]),
                        param_zone(300, search, "Search any column", mode="type_in")]),
    sheet_zone("Employee_Count", 30),
    sheet_zone("Employee_Table"),
], pad=16)]), 24, 160, CW, 916)
# Filter and legend panels float last, so they open above everything else.
home.float(filter_panel, 930, 92, 160, 56)
home.float(legend_panel, 1096, 92, 180, 56)

for key, title, *_ in METRICS:
    wb.set_param_on_click(home, f"KPI_{key}", F(emp, EM[key]["key"]), measure, f"{title} card sets the measure")
    wb.deselect_on_click(home, f"KPI_{key}", emp)
wb.set_param_on_click(home, "View_Toggle", vv, view, "Switch view")
wb.deselect_on_click(home, "View_Toggle", vw)
wb.set_param_on_click(home, "Employee_Table", F(tbl, "[column_name]"), sort, "Sort by column")
wb.deselect_on_click(home, "Employee_Table", tbl)

print(wb.save(OUT, DATA_DIR, twb_name="Diversity in Human Resources (Claude rebuild).twb"))
