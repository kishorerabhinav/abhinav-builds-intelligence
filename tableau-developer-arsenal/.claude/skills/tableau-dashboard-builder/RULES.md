# Rules Tableau enforces on generated workbooks

Each rule comes from an error Tableau raised on a generated .twbx. The builder
(`arsenal/dashboard_builder.py`) follows all of them and `tda twb check`
detects most of them.

## Schema errors ("value … not in enumeration", "element … is not allowed")

| Tableau said | Rule |
|---|---|
| `value 'all' not in enumeration` | A free-text parameter uses `param-domain-type='any'`. |
| `missing required attribute 'dim-percentage'` / `element 'layout' is not allowed` | Leave out the data source `<layout>` element. If kept, it goes before `<style>`. |
| `no declaration found for element 'clear-option'` | Don't write `<clear-option>` in parameter actions. |
| `element 'action' is not allowed for content model (action,datasources,datasource-dependencies*,edit-parameter-action)` | Inside `<actions>`: all `<action>`s, then `<datasources>`, then `<datasource-dependencies>`, then `<edit-parameter-action>`s. |
| `no declaration found for element 'label'` | There is no `label` encoding. The Label shelf is `<text>`. |
| `no declaration found for element 'computed-sort'` | Use `<sort class='computed' column=… direction='ASC' using=…/>`. |
| `element 'nodes' is not allowed for content model (properties,node-execution-subgraphs,…)` | The datagraph needs `<node-execution-subgraphs>` with a `<pair>` for every node. |

## "class std::out_of_range: invalid unordered_map<K, T> key"

A lookup by name or id failed while loading. Seen twice:

- **Parameter controls on a dashboard**: the dashboard must declare
  `<datasources><datasource name='Parameters' /></datasources>` and a
  `<datasource-dependencies datasource='Parameters'>` listing the parameters.
- **Dynamic zone visibility**: one `single-value-field-node` per zone (never
  share one field node across zones), every node listed in
  `node-execution-subgraphs`, `dashboard-identifier` = the dashboard's
  `simple-id`, `zone-id` = an existing zone.

## Opens, but looks wrong

| Symptom | Rule |
|---|---|
| Zones misplaced, overlapping, charts hidden behind cards | Floating zones were written inside the tiled layout. Write them as siblings of it inside `<zones>` (`Dashboard.float`), or use a tiled layout with fixed sizes. Backgrounds and borders go on containers. |
| Empty band at the bottom | Fix every height; flexible containers let Tableau redistribute space. |
| Default colours instead of yours | A colour palette needs the field declared as a `<column-instance>` on the data source, beside the palette in the data source `<style>`. |
| `<Parameters.X>` blank in a label or tooltip | The parameter must also be on the Marks card (an encoding). |
| Points that share an x value merge (a dash shows as a dot) | Give each point its own id and put it on Path. |
| `#######` instead of a number | The text doesn't fit its zone. Size the zone for the font (a 24pt number plus a 9pt caption needs about 80px), or use a smaller font. |
| Label colours ignored (default black) on a Square mark | Use a Text mark for coloured labels; put a tinted background on its container instead. |
| Bar labels drawn over the bar | Don't set the label's cell alignment; Tableau's default puts it after the bar when the axis leaves room. |
| A chart draws nothing, not even row headers, though the data matches its filter | Split-tested in Tableau on a bar chart with a dimension on Rows: numeric fields on the Marks card render (shares, counts, even when calculated with a parameter), but a field whose *text* comes from a parameter blanks the whole sheet: a calc that just returns a parameter (measure or year name), or a label like `STR(INT(year) - 1)`. Keep such fields off the Marks card; show numbers instead and put parameter text in dashboard text zones. |

## Layout, buttons and pictures (from a working Tableau Public workbook)

- Floating zones are siblings of the tiled layout inside `<zones>` (`Dashboard.float`), never
  children of it. A plain tiled background plus floating cards and controls is how the
  original HR dashboard is built.
- Show/hide switches are `dashboard-object` zones with a `<toggle-action>` naming the
  dashboard *window's* simple-id and the target zone id; export buttons name the
  *dashboard's* simple-id. Both need the BasicButtonObject / DashboardExportButton entries
  in the manifest (the builder adds them).
- Pictures and button images live in the .twbx under `Image/` (`Workbook.image`).
- Clickable icons: float the image(s), then float a transparent sheet over them whose marks
  carry a parameter action (the view switch). Swap dark/grey icons with zone visibility.
- Arrows that depend on a value go in a custom number format on a numeric field (`*▲ 0.0%`,
  `*▼ 0.0%;▼ 0.0%`, confirmed), not in a string calc, so Marks cards stay numeric. Keep letters
  out of number formats and put words in the label as static text.
- A year shown on a Marks card is a date with `*yyyy` (the original's `*mmmm yyyy` style).
  The number format `*0` displayed `#######`.
- A bar's label sits in free space only if the axis runs past the bar: for a track of 1.0,
  fix the axis at about 0–1.6 and the label lands to its right.

## House style used so far

- Fonts: Trebuchet MS for text, Georgia for large numbers and titles.
- String parameters for years (`"2022"`), compared with `INT()`, so they never
  display as `2,022`.
- Colours: the Claude dashboard palette (near-white page, white cards with hairline borders,
  blue accent, warm grey text, green / dark red for up / down).
- Helper CSVs carry month-by-month comparisons and rankings; Tableau only filters them.
- Sheet names without spaces when an action targets them (`KPI_Diversity`).
