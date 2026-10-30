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
| Zones misplaced, overlapping, charts hidden behind cards | Use a tiled layout (`layout-flow` containers) with fixed sizes, not floating zones. Backgrounds and borders go on containers. |
| Empty band at the bottom | Fix every height; flexible containers let Tableau redistribute space. |
| Default colours instead of yours | A colour palette needs the field declared as a `<column-instance>` on the data source, beside the palette in the data source `<style>`. |
| `<Parameters.X>` blank in a label or tooltip | The parameter must also be on the Marks card (an encoding). |
| Points that share an x value merge (a dash shows as a dot) | Give each point its own id and put it on Path. |
| A chart draws nothing, not even row headers, though the data matches its filter | Split-tested in Tableau: the same bar chart renders with an empty Marks card and goes blank once tooltip and label fields are added (data, filters, sort, formatting and the dual axis were all ruled out). Keep breakdown Marks cards empty and put the numbers in the row label as a string built from FIXED calcs. Which marks-card field is at fault is still open. |

## House style used so far

- Fonts: Trebuchet MS for text, Georgia for large numbers and titles.
- String parameters for years (`"2022"`), compared with `INT()`, so they never
  display as `2,022`.
- Helper CSVs carry anything layered or ranked; Tableau only filters them.
- Sheet names without spaces when an action targets them (`KPI_Diversity`).
