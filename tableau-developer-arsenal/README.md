# Tableau Developer Arsenal

Python scripts and clients for the everyday Tableau development loop: track a
Tableau Public portfolio, publish to Tableau Server or Cloud over the REST API,
inspect and lint workbooks, and build Hyper extracts.

## Where you can publish

| Target | How | Covered by |
|---|---|---|
| **Tableau Cloud / Server** | REST API with a personal access token | `tda server publish` |
| **Tableau Public** | Only through Tableau Public Desktop (*File > Save to Tableau Public*). Tableau Public has no publishing API. | `tda publish-public` opens the file there for you |

Tableau Public's profile API is read-only, but it's open: `tda public` uses it
for portfolio stats and images.

## Setup

```bash
cd tableau-developer-arsenal
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dotenv]"      # add ,hyper for Hyper extracts
copy .env.example .env          # then fill in your values
```

For Tableau Cloud or Server, create a personal access token under
**My Account Settings > Personal Access Tokens**. To find your Cloud site's
content URL, look in the browser address bar: `.../#/site/<content-url>/home`.

## Commands

### Tableau Public (no sign-in)

```bash
tda public profile --user kishorerabhinav
tda public stats --user kishorerabhinav                 # views, favourites, title
tda public stats --details --csv out/public_stats.csv   # adds publish dates and size
tda public image --workbook AutoSalesTrends             # default view, or add --view Overview
tda publish-public path\to\workbook.twbx                # opens Tableau Public Desktop
```

### Tableau Cloud / Server (REST API)

```bash
tda server whoami
tda server projects
tda server workbooks
tda server publish --file kpi.twbx --project "Portfolio"            # overwrites by default
tda server publish --file sales.hyper --project "Portfolio"         # data sources too
tda server download --name "Executive KPI"
tda server refresh --name "Executive KPI"
tda server export --name "Executive KPI" --view "Overview" --format pdf --filter Region=West
```

Files up to 64 MB are uploaded in one request. Larger files go through the
chunked `fileUploads` endpoint automatically.

### Local workbooks and data

```bash
tda twb inspect dashboard.twbx      # data sources, calcs, sheets, dashboards, parameters
tda twb lint dashboard.twb          # flags C:\... paths that break when shared (exit 1)
tda twb check dashboard.twbx        # finds what stops Tableau loading a generated workbook (exit 1)
tda twb package dashboard.twb --data data\sales.csv
tda hyper data\sales.csv --parse-dates order_date
```

## Building dashboards from Python

`arsenal.dashboard_builder` writes a packaged .twbx without Tableau Desktop:
data sources from CSV, parameters, calculated fields, worksheets, tiled
dashboards, dynamic zone visibility and click actions. Each XML convention in
it was checked against errors Tableau raised; they're listed in the skill's
[RULES.md](.claude/skills/tableau-dashboard-builder/RULES.md).

```bash
python examples/hr_diversity/prep_data.py examples/hr_diversity/data/hr_employees.csv out/hr_data
copy examples\hr_diversity\data\hr_employees.csv out\hr_data\
python examples/hr_diversity/build.py out/hr_data out/Diversity_in_HR.twbx
tda twb check out/Diversity_in_HR.twbx
```

The example rebuilds a Claude dashboard of the #RWFD HR diversity data in
the original Tableau Public workbook's colours. Open the result in Tableau
2023.1 or later.

### Claude skill

`.claude/skills/tableau-dashboard-builder/` teaches Claude the workflow:
shape the data in Python, build with the library, run `tda twb check`, then
iterate from what Tableau shows. Claude Code picks it up when working in this
folder; to use it elsewhere, copy the folder to `~/.claude/skills/`.

## Using it from Python

```python
from arsenal.config import ServerConfig
from arsenal.rest_client import TableauServer
from arsenal.public_api import TableauPublic

with TableauServer(ServerConfig.from_env()) as ts:
    wb = ts.publish_workbook("kpi.twbx", project="Portfolio")
    job = ts.refresh_workbook(wb["id"])

top = TableauPublic().stats("kishorerabhinav")[:5]
```

## Layout

```text
arsenal/
├── config.py          # env / .env settings
├── public_api.py      # Tableau Public profile API (read-only)
├── public_publish.py  # hand-off to Tableau Public Desktop
├── rest_client.py     # Server/Cloud REST: auth, browse, publish, download, refresh, export
├── workbook_tools.py  # .twb/.twbx inspect, lint, check, package
├── dashboard_builder.py  # write .twbx workbooks and dashboards from Python
├── hyper_tools.py     # CSV / DataFrame -> .hyper
└── cli.py             # `tda` command
examples/hr_diversity/ # data prep + build script for a full dashboard
.claude/skills/tableau-dashboard-builder/  # Claude skill: SKILL.md + RULES.md
```

## Tests

```bash
python -m unittest discover tests
```

The tests run offline. They cover workbook inspect, lint, check and package; building a workbook
with the dashboard builder and catching each load error Tableau has raised; a CSV to
Hyper round trip (skipped without `tableauhyperapi`); and the REST client
against a fake server: sign-in, pagination, single-request and chunked
publish, and errors.

## Notes

- The Tableau Public endpoints are undocumented, and their field names may change.
- Don't commit `.env`. It's already in `.gitignore`.
