---
name: tableau-dashboard-builder
description: Build a Tableau dashboard as a packaged .twbx from data and a design (a mock-up, a screenshot, a Claude dashboard or a description), using the arsenal's Python builder, without Tableau Desktop. Use when asked to create, rebuild, recolour or extend a Tableau workbook or dashboard, or to turn another dashboard into Tableau.
---

# Tableau dashboard builder

Claude can't run Tableau. You write the workbook XML with
`arsenal/dashboard_builder.py`, check it with `tda twb check`, and the person
opens it in Tableau Desktop or Tableau Public Desktop (2023.1 or later) and
tells you what they see. Every error and rendering fault Tableau has shown so
far is a rule in the builder and in [RULES.md](RULES.md), so build through the
library, not by hand-writing XML.

The worked example is `examples/hr_diversity/`: the Claude HR diversity
dashboard rebuilt in Tableau with an enterprise finish. It has a title block,
a view switch with clickable icons, Filters and Legends switches, four KPI cards
(progress bar, headline number, change chip, month-vs-year-before bars),
three breakdown charts with "View by" pickers, a side panel with logo and
export buttons, and an employee table with search and click-to-sort.

## Workflow

1. **Understand the data and the design.** Read the source data. If the
   design is another dashboard, list each element: headline figures, charts,
   filters, clicks, layout, colours (sample them from a screenshot) and fonts.
   If the person has the original .twbx, unzip it and read its XML: it shows
   how Tableau itself writes the layout, buttons, formats and images you need.
2. **Shape the data in Python, not in Tableau.** Anything Tableau draws
   awkwardly goes into small helper CSVs precomputed per selectable value
   (year, measure): month-by-month comparisons, rank columns for sorting,
   long-format tables. See `examples/hr_diversity/prep_data.py`.
3. **Build with the library** (`examples/hr_diversity/build.py` is the
   template): `Workbook` → `param` / `datasource` / `calc` → `worksheet` with
   `pane`s → `dashboard` with a plain tiled background and `float`ed cards and
   controls → `image`, `toggle_button`, `export_button` →
   `set_param_on_click` / `deselect_on_click` → `save`.
4. **Check before handing over:** `tda twb check out/your.twbx` must print no
   problems. Then give the person the .twbx.
5. **Iterate from what they see.**
   - A load error: ask for the exact text, map each line to RULES.md, fix the
     builder or your script, and add a case to `check_workbook` if it is new.
   - Opens but something is blank or wrong: don't guess twice. Send a split
     test (one dashboard with the chart drawn several ways, each dropping one
     feature) and ask which versions render.
   - When the person sends back a .twbx Tableau has re-saved, read it: it shows
     how Tableau parsed every data source, field and sheet.
   - Record what you learn in RULES.md so the next build gets it right.

## What is proven to render

Checked in Tableau with the HR example:

- **Layout:** a plain tiled background with floating cards and controls
  written as siblings of the tiled layout (`Dashboard.float`); containers with
  fixed sizes, backgrounds, borders and padding inside the floats.
- **Text sheets** with customised labels mixing numeric fields, fonts and
  colours: headline numbers, summary sentences, change chips whose arrows come
  from number formats (`*▲ 0.0%`, `*▼ 0.0%;▼ 0.0%`).
- **Bars:** dual-axis grey track and coloured bar (progress bars, breakdowns)
  with value labels after the bar and a custom tooltip; dual-axis
  this-month-vs-year-before bars from a helper CSV.
- **Lines:** dual-axis line + area with a palette by layer and a path for dashes.
- **Controls:** parameter controls, parameter actions on click with the
  deselect trick, a click-to-switch view sheet floated over its icons, show/hide
  switch buttons with images, PDF and PowerPoint export buttons.
- **Dynamic zone visibility** on containers, blank zones and images (views,
  selected-card strips, icons that turn dark or grey with the view).

Avoid, both confirmed in Tableau:

- A field whose *text* comes from a parameter on a Marks card (a calc that
  returns a parameter, `STR(INT(year) - 1)`): the whole sheet draws nothing.
  Keep Marks cards numeric and put parameter text in dashboard text zones.
- Gantt layers from a helper CSV filtered by parameter comparisons: drew nothing.

Not yet confirmed: the Excel (crosstab) export button showed greyed out.

## Hand-over message

Say what the workbook contains, that you couldn't open it in Tableau, which
Tableau version it needs, and what to send back if it fails: the exact error
text, or a screenshot plus **Go to Sheet** on anything blank.
