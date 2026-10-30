---
name: tableau-dashboard-builder
description: Build a Tableau dashboard as a packaged .twbx from data and a design (a mock-up, a screenshot, a Claude dashboard or a description), using the arsenal's Python builder, without Tableau Desktop. Use when asked to create, rebuild, recolour or extend a Tableau workbook or dashboard, or to turn another dashboard into Tableau.
---

# Tableau dashboard builder

Claude can't run Tableau. You write the workbook XML with
`arsenal/dashboard_builder.py`, check it with `tda twb check`, and the person
opens it in Tableau Desktop or Tableau Public Desktop (2023.1 or later) and
tells you what they see. Every load error Tableau has raised so far is a
rule in the builder and in [RULES.md](RULES.md), so build through the
library, not by hand-writing XML.

A complete worked example lives in `examples/hr_diversity/`: four KPI
cards with trends, three breakdown charts, an Overview / Employee list
switch, click-to-filter cards and a sortable table.

## Workflow

1. **Understand the data and the design.** Read the source data. If the
   design is another dashboard, list each element: headline figures, charts,
   filters, clicks, layout, colours (sample them from a screenshot) and fonts.
2. **Shape the data in Python, not in Tableau.** Anything the design needs
   that Tableau draws awkwardly goes into small helper CSVs: layered charts,
   rank columns for sorting, long-format tables. Precompute per selectable
   value (year, measure, grouping) so Tableau only filters. See
   `examples/hr_diversity/prep_data.py`.
3. **Build with the library** (`examples/hr_diversity/build.py` is the
   template): `Workbook` → `param` / `datasource` / `calc` → `worksheet`
   with `pane`s → `dashboard` with a tiled `N` layout → `set_param_on_click`
   / `deselect_on_click` → `save`.
4. **Check before handing over:** `tda twb check out/your.twbx`. It must print
   no problems. Then give the person the .twbx.
5. **Iterate from what they see.**
   - A load error: ask for the exact text, map each line to RULES.md, fix the
     builder or your script, and add a case to `check_workbook` if it is new.
   - Opens but something is blank or wrong: don't guess twice. Build a
     split test (a copy that adds one part at a time, or one dashboard with
     the same chart drawn several ways) and ask which ones render.
   - Record what you learn in RULES.md so the next build gets it right.

## What is proven to render

Checked in Tableau with the HR example:

- Tiled layout with fixed heights, container backgrounds, borders and padding.
- Text sheets with customised labels mixing fields, parameters and fonts
  (headline numbers, change arrows coloured by direction, sentences).
- Dual-axis line + area with a colour palette by layer, a path for dashes,
  labels from the Text shelf, fixed hidden axes.
- Parameter controls, parameter actions on click, the deselect trick.
- Dynamic zone visibility on containers and blank zones (views, selected-card
  strips).

Not yet confirmed: Gantt-bar layers filtered by a parameter comparison (the
breakdown charts drew nothing). `examples/hr_diversity` keeps them until the
split test decides between "Gantt" and "parameter filter"; prefer plain bars
or dual-axis bars until then.

## Hand-over message

Say what the workbook contains, that you couldn't open it in Tableau, which
Tableau version it needs, and what to send back if it fails: the exact error
text, or a screenshot plus **Go to Sheet** on anything blank.
