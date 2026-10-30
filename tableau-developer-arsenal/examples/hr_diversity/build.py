"""Diversity in Human Resources: the Claude dashboard rebuilt as a Tableau workbook.

    python examples/hr_diversity/prep_data.py examples/hr_diversity/data/hr_employees.csv out/hr_data
    copy examples\\hr_diversity\\data\\hr_employees.csv out\\hr_data\\   (the employee rows are a data source too)
    python examples/hr_diversity/build.py out/hr_data out/Diversity_in_HR.twbx
    tda twb check out/Diversity_in_HR.twbx

Data: Real World Fake Data (#RWFD) HR diversity dataset, one row per employee.
Colours are the original Tableau Public workbook's palette.
"""

from __future__ import annotations

import sys

from arsenal.dashboard_builder import (SERIF, F, N, Workbook, blank_zone, fixed_axis, pane, param_zone, runs,
                                       sheet_zone, text_zone)

DATA_DIR, OUT = sys.argv[1], sys.argv[2]

BAND, PAGE, CARD = "#eee6d8", "#e8ebee", "#ffffff"
GOLD, RED, INK, MUTED = "#cea25a", "#ce4e35", "#333333", "#757781"
BORDER, TRACK, TICK, RULE, GUIDE = "#e0dcd3", "#f2f1ee", "#7f818d", "#b9b6ad", "#cfcbc1"

wb = Workbook(data_folder="Data/hr-dashboard")

year = wb.param("Hiring year", "2022", ["2022", "2021", "2020", "2019", "2018"])
measure = wb.param("Measure", "Diversity", ["Diversity", "Persons of color", "Female", "Male & NA"])
role_by = wb.param("Group roles by", "Position", ["Position", "Department", "Job role"])
bg_by = wb.param("Group background by", "Education", ["Education", "Education field", "Race", "Marital status"])
perf_by = wb.param("Group performance by", "Performance rating", ["Performance rating", "Employee satisfaction"])
search = wb.param("Search", "")
view = wb.param("View", "Overview", ["Overview", "Employee list"])
sort = wb.param("Sort", "Hire date|asc")
YEAR_N = f"INT({year.ref})"

emp = wb.datasource("0hrclaudeemp001", "HR Employees", "hr_employees.csv", [
    ("employee_id", "string"), ("hire_date", "date"), ("gender", "string"), ("poc", "string"), ("race", "string"),
    ("diverse", "string"), ("position", "string"), ("department", "string"), ("job_role", "string"),
    ("performance", "string"), ("satisfaction", "integer"), ("education", "string"), ("education_field", "string"),
    ("marital_status", "string")])
trd = wb.datasource("0hrclaudetrd001", "Monthly trend layers", "trend.csv", [
    ("sel_year", "string"), ("metric", "string"), ("layer", "string"), ("seg", "string"), ("month", "date"),
    ("value", "real"), ("area", "real"), ("label", "string"), ("hires", "integer"), ("pt", "string")])
tbl = wb.datasource("0hrclaudetbl001", "Employee table", "employee_table.csv", [
    ("employee_id", "string"), ("hire_year", "integer"), ("column_name", "string"), ("col_order", "integer"),
    ("value", "string"), ("value_rank", "integer")])
vw = wb.datasource("0hrclaudevw0001", "Views", "views.csv", [("view", "string"), ("view_order", "integer")])

# -- calculations ----------------------------------------------------------

METRICS = [  # sheet key, title, definition, row test, colour the change by direction
    ("Diversity", "Diversity", "Female or a person of color", "[diverse] = 'Diverse'", True),
    ("POC", "Persons of color", "Any race other than White", "[poc] = 'POC'", True),
    ("Female", "Female", "Gender recorded as female", "[gender] = 'Female'", True),
    ("MaleNA", "Male & NA", "Male or gender not recorded", "[gender] = 'Male & NA'", False),
]
period = emp.calc("Period", "string", f"IF YEAR([hire_date]) = {YEAR_N} THEN 'Current'\nELSEIF YEAR([hire_date]) = {YEAR_N} - 1 THEN 'Previous'\nEND")
cy_hires = emp.calc("CY hires", "integer", f"SUM(IF {period} = 'Current' THEN 1 ELSE 0 END)", fmt="n#,##0")
prev_year = emp.calc("Previous year", "string", f"STR({YEAR_N} - 1)")
EM = {}
for key, title, _, cond, _ in METRICS:
    m = {}
    m["cy"] = emp.calc(f"CY {title} %", "real", f"SUM(IF {period} = 'Current' AND {cond} THEN 1 ELSE 0 END)\n"
                       f"/ SUM(IF {period} = 'Current' THEN 1 ELSE 0 END)", fmt="p0.0%")
    m["py"] = emp.calc(f"PY {title} %", "real", f"SUM(IF {period} = 'Previous' AND {cond} THEN 1 ELSE 0 END)\n"
                       f"/ SUM(IF {period} = 'Previous' THEN 1 ELSE 0 END)", fmt="p0.0%")
    m["chg"] = emp.calc(f"{title} change (pts)", "real", f"({m['cy']} - {m['py']}) * 100", fmt="n#,##0.0")
    pts = f"STR(ROUND({m['chg']}, 1)) + ' pts'"
    m["up"] = emp.calc(f"{title} change up", "string", f"IIF({m['chg']} >= 0.05, '▲ +' + {pts}, '')", role="measure")
    m["down"] = emp.calc(f"{title} change down", "string", f"IIF({m['chg']} <= -0.05, '▼ ' + {pts}, '')", role="measure")
    m["flat"] = emp.calc(f"{title} change flat", "string", f"IIF(ABS({m['chg']}) < 0.05, '±0.0 pts', '')", role="measure")
    m["vs"] = emp.calc(f"{title} vs label", "string", f"' vs ' + STR(ROUND({m['py']} * 100, 1)) + '% in ' + STR({YEAR_N} - 1)", role="measure")
    m["key"] = emp.calc(f"{title} measure key", "string", f"'{title}'")
    m["sel"] = emp.calc(f"Show {title} as selected", "boolean", f"{view.ref} = 'Overview' AND {measure.ref} = '{title}'")
    m["unsel"] = emp.calc(f"Show {title} as not selected", "boolean", f"{view.ref} = 'Overview' AND {measure.ref} <> '{title}'")
    EM[key] = m
dv = EM["Diversity"]
direction = emp.calc("Diversity direction text", "string",
                     f"IIF({dv['chg']} >= 0, 'up ', 'down ') + STR(ROUND(ABS({dv['chg']}), 1)) + ' pts'", role="measure")
show_overview = emp.calc("Show overview", "boolean", f"{view.ref} = 'Overview'")
show_table = emp.calc("Show employee list", "boolean", f"{view.ref} = 'Employee list'")

# Breakdowns read the employee rows, like the KPI cards: shares for the chosen measure and
# year, grouped by whichever field the card's "Group by" picker names.
def by_measure(part):
    return f"CASE {measure.ref}\n" + "\n".join(f"WHEN '{t}' THEN {EM[k][part]}" for k, t, *_ in METRICS) + "\nEND"


in_window = emp.calc("In comparison window", "boolean", f"NOT ISNULL({period})")
cy_sel = emp.calc("CY selected %", "real", by_measure("cy"), fmt="p0.0%")
py_sel = emp.calc("PY selected %", "real", by_measure("py"), fmt="p0.0%")
# 1 when the person counts towards the chosen measure. A CASE that returns true/false made
# every sheet using it draw nothing, so it returns numbers.
picked = f"CASE {measure.ref}\n" + "\n".join(f"WHEN '{t}' THEN IIF({c}, 1, 0)" for _, t, _, c, _ in METRICS) + "\nEND"
cy_count = emp.calc("CY selected count", "integer", f"SUM(IF {period} = 'Current' THEN {picked} ELSE 0 END)", fmt="n#,##0")
track = emp.calc("Track", "real", "MIN(1.0)")
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
GROUPS = {}
for card, (picker, options) in GROUPINGS.items():
    group = emp.calc(f"{card} group", "string", f"CASE {picker.ref}\n" + "\n".join(f"WHEN '{v}' THEN {f}" for v, f in options) + "\nEND")
    hires = emp.calc(f"{card} group hires", "integer", f"{{FIXED {group} : SUM(IIF(YEAR([hire_date]) = {YEAR_N}, 1, 0))}}")
    label = emp.calc(f"{card} group label", "string", f"{group} + ' (' + STR({hires}) + ')'")
    hired = emp.calc(f"{card} group hired this year", "boolean", f"{hires} > 0")
    lit = lambda v: f'"{v}"' if "'" in v else f"'{v}'"  # Master's Degree goes in double quotes
    ranked = [(v, f) for v, f in options if v in ORDERS]
    listed = "".join(f"\nWHEN '{v}' THEN CASE {f}" + "".join(f" WHEN {lit(x)} THEN {i}" for i, x in enumerate(ORDERS[v], 1)) + " ELSE 90 END"
                     for v, f in ranked)
    is_ranked = " OR ".join(f"{picker.ref} = '{v}'" for v, _ in ranked) or "FALSE"
    # Ranked fields keep their listed order (Vice President first); others go largest share first.
    # "Not recorded" always sorts last.
    sort_key = emp.calc(f"{card} sort", "real",
                        f"MIN(IIF({group} = 'Not recorded', 1000, 0))\n"
                        f"+ MIN(CASE {picker.ref}{listed}\nELSE 0 END)\n"
                        f"+ IIF({is_ranked}, 0, -{cy_sel})")
    GROUPS[card] = dict(label=label, hired=hired, sort=sort_key)

trend_year = trd.calc("Selected year rows", "boolean", f"[sel_year] = {year.ref}")
trd.palette("[layer]", {"Share": GOLD, "End": GOLD, "Boundary": RULE, "Guide": GUIDE, "Label": CARD})

sortcol = f"LEFT({sort.ref}, FIND({sort.ref}, '|') - 1)"
desc = f"ENDSWITH({sort.ref}, '|desc')"
t_year = tbl.calc("Hired in selected year", "boolean", f"[hire_year] = {YEAR_N}")
t_search = tbl.calc("Matches search", "boolean",
                    f"{search.ref} = '' OR {{FIXED [employee_id] : MAX(IIF(CONTAINS(LOWER([value]), LOWER({search.ref})), 1, 0))}} = 1")
t_head = tbl.calc("Column heading", "string", f"[column_name] + IIF({sortcol} = [column_name], IIF({desc}, ' ▼', ' ▲'), '')")
t_next = tbl.calc("Next sort", "string", f"[column_name] + IIF({sortcol} = [column_name] AND NOT {desc}, '|desc', '|asc')")
t_sortval = tbl.calc("Row sort value", "integer", f"IIF([column_name] = {sortcol}, [value_rank] * IIF({desc}, -1, 1), NULL)")
t_people = tbl.calc("People shown", "integer", "COUNTD([employee_id])", fmt="n#,##0")

v_on = vw.calc("Is current view", "string", f"IIF([view] = {view.ref}, 'on', 'off')")
vw.palette(v_on, {"on": INK, "off": MUTED})

# -- worksheets ------------------------------------------------------------

LEFT_TOP = "<style-rule element='cell'><format attr='text-align' value='left' /><format attr='vertical-align' value='top' /></style-rule>"
LEFT_MID = "<style-rule element='cell'><format attr='text-align' value='left' /><format attr='vertical-align' value='center' /></style-rule>"
mut, bold = {"fontcolor": MUTED, "fontsize": 11}, {"fontcolor": INK, "fontsize": 11, "bold": "true"}

cyn, dcy, ddir, pyr = F(emp, cy_hires), F(emp, dv["cy"]), F(emp, direction), F(emp, prev_year)
wb.worksheet("Summary", emp, tooltip_none=True, panes=[pane(
    "Text", enc=[("text", cyn), ("text", dcy), ("text", ddir), ("text", pyr), ("text", year)], cell=LEFT_MID,
    mark_fmt={"mark-labels-show": "true"},
    label=runs([("Of the ", mut), (cyn, bold), (" people hired in ", mut), (year, bold), (", ", mut), (dcy, bold),
                (" were diverse (female or a person of color), ", mut), (ddir, bold), (" on the ", mut), (pyr, bold),
                (" hiring class.", mut)]))])

zero, one = emp.zero_one()
for key, title, _, _, coloured in METRICS:
    m = EM[key]
    cy, up, dn, fl, vs = (F(emp, m[k]) for k in ("cy", "up", "down", "flat", "vs"))
    up_c, dn_c = (GOLD, RED) if coloured else (MUTED, MUTED)
    wb.worksheet(f"KPI_{key}", emp, tooltip_none=True, panes=[pane(
        "Text", cell=LEFT_TOP, mark_fmt={"mark-labels-show": "true"},
        enc=[("lod", F(emp, m["key"])), ("lod", F(emp, zero)), ("lod", F(emp, one)), ("text", cy), ("text", up),
             ("text", dn), ("text", fl), ("text", vs)],
        label=runs([(cy, {"fontcolor": INK, "fontsize": 28, "fontname": SERIF}), "\n",
                    (up, {"fontcolor": up_c, "fontsize": 9, "bold": "true"}), (dn, {"fontcolor": dn_c, "fontsize": 9, "bold": "true"}),
                    (fl, {"fontcolor": MUTED, "fontsize": 9, "bold": "true"}), (vs, {"fontcolor": MUTED, "fontsize": 9})]))])

for key, title, *_ in METRICS:
    month, val, area = F(trd, "[month]", "none", "qk"), F(trd, "[value]", "sum"), F(trd, "[area]", "sum")
    layer, seg, lab, hires, pt = F(trd, "[layer]"), F(trd, "[seg]"), F(trd, "[label]"), F(trd, "[hires]", "sum"), F(trd, "[pt]")
    tip = runs([(month, {"fontcolor": MUTED, "fontsize": 9}), "\n", (f"{title} ", {"fontcolor": INK, "fontsize": 10}),
                (val, {"fontcolor": INK, "fontsize": 10, "bold": "true"}), "\n", (hires, {"fontcolor": MUTED, "fontsize": 9}),
                (" hires", {"fontcolor": MUTED, "fontsize": 9})])
    line_enc = [("color", layer), ("lod", seg), ("path", pt), ("text", lab), ("tooltip", hires)]
    wb.worksheet(f"Trend_{key}", trd, cols=[month], rows=[val, area], dual_rows=True,
                 filters=[(F(trd, trend_year), "true"), (F(trd, "[metric]"), f'"{title}"')],
                 panes=[pane("Line", enc=line_enc, tooltip=tip),
                        pane("Line", enc=line_enc, tooltip=tip, pane_id=1, axis=val, axis_attr="y-axis-name",
                             mark_fmt={"mark-labels-show": "true", "mark-labels-cull": "false", "size": "0.5"},
                             extra_style=f"<style-rule element='datalabel'><format attr='color-mode' value='user' />"
                                         f"<format attr='color' value='{MUTED}' /><format attr='font-size' value='8' /></style-rule>"),
                        pane("Area", enc=[("tooltip", hires)], tooltip=tip, pane_id=2, axis=area, axis_attr="y-axis-name",
                             mark_fmt={"mark-color": GOLD, "mark-transparency": "45"})],
                 style="<style-rule element='axis'>" + fixed_axis(val, -0.16, 1.02, "rows") + fixed_axis(area, -0.16, 1.02, "rows", sync=True)
                       + f"<format attr='display' class='0' field='{month.ref}' scope='cols' value='false' /></style-rule>")

def breakdown_sheet(name, card):
    """Grey track and gold bar per group, labelled with this year's share and the year before.

    Split-tested in Tableau: numeric fields on the Marks card are fine, but a field whose text
    comes from a parameter (the measure or year name, "% in 2021") made the whole sheet blank.
    """
    g = GROUPS[card]
    row, order = F(emp, g["label"]), F(emp, g["sort"])
    trk, cy, py, cnt = F(emp, track), F(emp, cy_sel), F(emp, py_sel), F(emp, cy_count)
    tips = [("tooltip", cnt), ("tooltip", py)]
    tip = runs([(row, {"fontcolor": MUTED, "fontsize": 9}), "\n", ("This year: ", {"fontcolor": INK, "fontsize": 10}),
                (cy, {"fontcolor": INK, "fontsize": 10, "bold": "true"}), "\n", (cnt, {"fontcolor": MUTED, "fontsize": 9}),
                (" hires in this group counted", {"fontcolor": MUTED, "fontsize": 9}), "\n",
                ("Year before: ", {"fontcolor": MUTED, "fontsize": 9}), (py, {"fontcolor": MUTED, "fontsize": 9})])
    label = runs([(cy, {"fontcolor": INK, "fontsize": 9, "bold": "true"}), ("  vs ", {"fontcolor": MUTED, "fontsize": 8}),
                  (py, {"fontcolor": MUTED, "fontsize": 8})])
    style = ("<style-rule element='axis'>" + fixed_axis(trk, 0, 1.0, "cols") + fixed_axis(cy, 0, 1.0, "cols", sync=True) + "</style-rule>"
             f"<style-rule element='header'><format attr='width' field='{row.ref}' value='175' /></style-rule>"
             f"<style-rule element='label'><format attr='font-size' field='{row.ref}' value='9' />"
             f"<format attr='color' field='{row.ref}' value='{INK}' /></style-rule>")
    wb.worksheet(name, emp, rows=[row], cols=[trk, cy], dual_cols=True, sorts=[(row, order)],
                 filters=[(F(emp, in_window), "true"), (F(emp, g["hired"]), "true")], style=style,
                 panes=[pane("Bar", enc=tips, tooltip=tip),
                        pane("Bar", enc=tips, tooltip=tip, pane_id=1, axis=trk,
                             mark_fmt={"mark-color": TRACK, "size": "1.6", "has-stroke": "false"}),
                        pane("Bar", enc=tips + [("text", cy), ("text", py)], tooltip=tip, pane_id=2, axis=cy, label=label,
                             mark_fmt={"mark-color": GOLD, "size": "1.6", "has-stroke": "false",
                                       "mark-labels-show": "true", "mark-labels-cull": "false"})])


for card in ("Role", "Background", "Performance"):
    breakdown_sheet(f"By_{card}", card)

vv, vo = F(vw, "[view]"), F(vw, "[view_order]", "min")
vz, v1 = vw.zero_one()
wb.worksheet("View_Toggle", vw, cols=[vv], sorts=[(vv, vo)], tooltip_none=True,
             panes=[pane("Text", enc=[("text", vv), ("color", F(vw, v_on)), ("lod", F(vw, vz)), ("lod", F(vw, v1))],
                         mark_fmt={"mark-labels-show": "true"},
                         label=runs([(vv, {"fontsize": 10, "bold": "true"})]),
                         cell="<style-rule element='cell'><format attr='text-align' value='center' /><format attr='vertical-align' value='center' /></style-rule>")],
             style=f"<style-rule element='header'><format attr='height-header' value='1' /></style-rule>"
                   f"<style-rule element='label'><format attr='color' field='{vv.ref}' value='#00000000' /><format attr='font-size' field='{vv.ref}' value='1' /></style-rule>")

tz, t1 = tbl.zero_one()
emp_id, head, value = F(tbl, "[employee_id]"), F(tbl, t_head), F(tbl, "[value]")
tfilters = [(F(tbl, t_year), "true"), (F(tbl, t_search), "true")]
wb.worksheet("Employee_Table", tbl, rows=[emp_id], cols=[head], filters=tfilters, tooltip_none=True,
             sorts=[(emp_id, F(tbl, t_sortval, "min")), (head, F(tbl, "[col_order]", "min"))],
             panes=[pane("Text", enc=[("text", value), ("lod", F(tbl, t_next)), ("lod", F(tbl, tz)), ("lod", F(tbl, t1))],
                         mark_fmt={"mark-labels-show": "true"}, label=runs([(value, {"fontcolor": INK, "fontsize": 9})]), cell=LEFT_MID)],
             style=f"<style-rule element='header'><format attr='width' field='{emp_id.ref}' value='1' /><format attr='height-header' value='30' />"
                   f"<format attr='band-color' scope='rows' value='#f7f5f0' /></style-rule>"
                   f"<style-rule element='label'><format attr='color' field='{emp_id.ref}' value='#00000000' /><format attr='font-size' field='{head.ref}' value='9' />"
                   f"<format attr='color' field='{head.ref}' value='{INK}' /><format attr='font-weight' field='{head.ref}' value='bold' /></style-rule>")
ppl = F(tbl, t_people)
wb.worksheet("Employee_Count", tbl, filters=tfilters, tooltip_none=True,
             panes=[pane("Text", enc=[("text", ppl)], cell=LEFT_MID, mark_fmt={"mark-labels-show": "true"},
                         label=runs([(ppl, {"fontcolor": INK, "fontsize": 9, "bold": "true"}),
                                     (" people shown. Select a column heading to sort; select it again to reverse.", {"fontcolor": MUTED, "fontsize": 9})]))])

# -- dashboard ---------------------------------------------------------------

W, H = 1300, 1100
BODY = H - 172
home = wb.dashboard("Home", W, H, background=PAGE)


def kpi_card(key, title, definition):
    m = EM[key]
    return N("vert", None, bg=CARD, border=BORDER, pad=12, kids=[
        blank_zone(3, bg=INK, show=(emp.ref(m["sel"]), title == "Diversity")),
        blank_zone(3, bg=BORDER, show=(emp.ref(m["unsel"]), title != "Diversity")),
        blank_zone(6),
        text_zone(22, [(title, {"fontcolor": INK, "fontsize": 12, "bold": "true"})]),
        text_zone(20, [(definition, {"fontcolor": MUTED, "fontsize": 9})]),
        sheet_zone(f"KPI_{key}", 78),
        sheet_zone(f"Trend_{key}"),
    ])


def breakdown_card(card, heading, param):
    return N("vert", None, bg=CARD, border=BORDER, pad=12, kids=[
        text_zone(26, [(measure, {"fontcolor": INK, "fontsize": 12, "bold": "true"}), (f" by {heading}", {"fontcolor": INK, "fontsize": 12, "bold": "true"})]),
        N("horz", 46, kids=[
            text_zone(None, [("Share of ", {"fontcolor": MUTED, "fontsize": 9}), (year, {"fontcolor": MUTED, "fontsize": 9}),
                             (" hires in each group, with the year before in grey.", {"fontcolor": MUTED, "fontsize": 9})]),
            param_zone(150, param, "Group by"),
        ]),
        sheet_zone(f"By_{card}"),
    ])


def spaced(items, gap=16):
    out = []
    for i, item in enumerate(items):
        if i:
            out.append(blank_zone(gap))
        out.append(item)
    return out


header = N("vert", 172, bg=BAND, pad=20, kids=[
    text_zone(46, [("Diversity in Human Resources", {"fontcolor": INK, "fontsize": 26, "fontname": SERIF})]),
    sheet_zone("Summary", 34),
    N("horz", 52, kids=[param_zone(190, year, "Hiring year"), blank_zone(16), sheet_zone("View_Toggle", 260, border="#d6cdbb"), blank_zone()]),
])
overview = N("vert", BODY, pad=20, show=(emp.ref(show_overview), True), kids=[
    N("horz", 250, kids=spaced([kpi_card(k, t, d) for k, t, d, *_ in METRICS])),
    blank_zone(8),
    text_zone(36, [("Each card is the share of that year's hires, with the change in percentage points from the year before. "
                    "The line shows each month's hires over the two years; the dashed line marks the new year. "
                    "Pick a card to show it in the charts below.", {"fontcolor": MUTED, "fontsize": 9})]),
    N("horz", BODY - 40 - 250 - 8 - 36 - 8 - 40, kids=spaced([breakdown_card("Role", "role", role_by),
                                                             breakdown_card("Background", "background", bg_by),
                                                             breakdown_card("Performance", "performance", perf_by)])),
    blank_zone(8),
    text_zone(40, [('"Not recorded" groups people whose department, job role, education or marital status is blank in the source data. '
                    "Hiring years 2018 to 2022 are offered because each has a full year before it to compare with. "
                    "Data: Real World Fake Data (#RWFD) HR diversity dataset.", {"fontcolor": MUTED, "fontsize": 8})]),
])
table_view = N("vert", BODY, pad=20, show=(emp.ref(show_table), False), kids=[
    N("vert", BODY - 40, bg=CARD, border=BORDER, pad=16, kids=[
        N("horz", 48, kids=[text_zone(None, [("People hired in ", {"fontcolor": INK, "fontsize": 13, "bold": "true"}),
                                             (year, {"fontcolor": INK, "fontsize": 13, "bold": "true"})]),
                            param_zone(300, search, "Search any column", mode="type_in")]),
        sheet_zone("Employee_Count", 30),
        sheet_zone("Employee_Table"),
    ]),
])
home.root = N("vert", None, kids=[header, overview, table_view])

for key, title, *_ in METRICS:
    wb.set_param_on_click(home, f"KPI_{key}", F(emp, EM[key]["key"]), measure, f"{title} card sets the measure")
    wb.deselect_on_click(home, f"KPI_{key}", emp)
wb.set_param_on_click(home, "View_Toggle", vv, view, "Switch view")
wb.deselect_on_click(home, "View_Toggle", vw)
wb.set_param_on_click(home, "Employee_Table", F(tbl, t_next), sort, "Sort by column")
wb.deselect_on_click(home, "Employee_Table", tbl)

print(wb.save(OUT, DATA_DIR, twb_name="Diversity in Human Resources (Claude rebuild).twb"))
