"""Offline tests: workbook tools, Hyper extracts and the REST client against a fake server.

Run with: python -m unittest discover tests
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

import requests

from arsenal import rest_client, workbook_tools as wt
from arsenal.config import ServerConfig
from arsenal.rest_client import TableauServer

FIXTURE = Path(__file__).parent / "fixtures" / "sample.twb"


class WorkbookToolsTest(unittest.TestCase):
    def test_inspect(self):
        info = wt.inspect_workbook(FIXTURE)
        self.assertEqual(info["worksheets"], ["Sales by Region", "Profit Trend"])
        self.assertEqual(info["dashboards"], ["Overview"])
        self.assertEqual(info["parameters"], ["Target Margin"])
        [ds] = info["datasources"]  # Parameters and the worksheet reference are skipped
        self.assertEqual(ds["name"], "Sales")
        self.assertEqual(ds["connections"], ["textscan"])
        self.assertEqual(ds["calculated_fields"],
                         [{"name": "Profit Ratio", "formula": "SUM([Profit]) / SUM([Sales])"}])

    def test_lint_finds_absolute_paths(self):
        self.assertEqual(wt.find_hardcoded_paths(FIXTURE), ["C:/Users/someone/Desktop/data"])

    def test_package_and_inspect_twbx(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "sales.csv"
            data.write_text("Region,Sales\nWest,10\n")
            twbx = wt.package_twbx(FIXTURE, [data], Path(tmp) / "sample.twbx")
            with zipfile.ZipFile(twbx) as zf:
                self.assertEqual(sorted(zf.namelist()), ["Data/sales.csv", "sample.twb"])
            self.assertEqual(wt.inspect_workbook(twbx)["dashboards"], ["Overview"])


class DashboardBuilderTest(unittest.TestCase):
    """A small workbook with every feature the builder writes, checked like Tableau would load it."""

    def build(self, tmp: Path) -> Path:
        from arsenal.dashboard_builder import F, N, Workbook, blank_zone, pane, param_zone, runs, sheet_zone

        (tmp / "sales.csv").write_text("region,sales\nWest,10\nEast,5\n")
        wb = Workbook()
        region = wb.param("Region", "West", ["West", "East"])
        view = wb.param("View", "Chart", ["Chart", "Table"])
        ds = wb.datasource("sales001", "Sales", "sales.csv", [("region", "string"), ("sales", "real")])
        picked = ds.calc("Picked region", "boolean", f"[region] = {region.ref}")
        show_chart = ds.calc("Show chart", "boolean", f"{view.ref} = 'Chart'")
        ds.palette("[region]", {"West": "#cea25a", "East": "#7f818d"})
        zero, one = ds.zero_one()
        reg, sales = F(ds, "[region]"), F(ds, "[sales]", "sum")
        wb.worksheet("Bars", ds, rows=[reg], cols=[sales], filters=[(F(ds, picked), "true")], sorts=[(reg, sales)],
                     panes=[pane("Bar", enc=[("color", reg), ("text", sales), ("lod", F(ds, zero)), ("lod", F(ds, one)), ("tooltip", region)],
                                 label=runs([(sales, {"bold": "true"}), (" in ", {}), (region, {})]))])
        dash = wb.dashboard("Home", 800, 600)
        dash.root = N("vert", None, kids=[param_zone(50, region, "Region"), blank_zone(10),
                                          sheet_zone("Bars", show=(ds.ref(show_chart), True))])
        wb.set_param_on_click(dash, "Bars", reg, region, "Pick region")
        wb.deselect_on_click(dash, "Bars", ds)
        return wb.save(tmp / "built.twbx", tmp)

    def test_build_passes_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            twbx = self.build(Path(tmp))
            self.assertEqual(wt.check_workbook(twbx), [])
            info = wt.inspect_workbook(twbx)
            self.assertEqual((info["worksheets"], info["dashboards"], info["parameters"]), (["Bars"], ["Home"], ["Region", "View"]))
            with zipfile.ZipFile(twbx) as zf:
                self.assertIn("Data/datasources/sales.csv", zf.namelist())
                root = ET.fromstring(zf.read("built.twb"))
            self.assertEqual([c.tag for c in root.find("actions")],
                             ["action", "datasources", "datasource-dependencies", "edit-parameter-action"])
            self.assertIsNotNone(root.find("datagraph/graph/node-execution-subgraphs"))

    def test_check_catches_what_tableau_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            twbx = self.build(Path(tmp))
            with zipfile.ZipFile(twbx) as zf:
                xml = zf.read("built.twb").decode()
            broken = Path(tmp) / "broken.twb"
            cases = {
                "not declared on the dashboard": lambda s: re.sub(r"(<size [^>]*/>)<datasources>.*?(?=<zones>)", r"\1", s),
                "rejected by older loaders": lambda s: s.replace("<sort class='computed'", "<computed-sort", 1).replace("<agg-type type='attr' />", "<agg-type type='attr' /><clear-option type='do-nothing' />"),
                "param-domain-type='all'": lambda s: s.replace("param-domain-type='list'", "param-domain-type='all'", 1),
                "<label> is not an encoding": lambda s: s.replace("<tooltip column=", "<label column=", 1),
                "node-execution-subgraphs": lambda s: re.sub(r"<node-execution-subgraphs>.*?</node-execution-subgraphs>", "", s),
                "missing sheet": lambda s: s.replace("name=\"Bars\" show-title", "name=\"Gone\" show-title"),
            }
            for expected, mutate in cases.items():
                broken.write_text(mutate(xml))
                problems = wt.check_workbook(broken)
                self.assertTrue(any(expected in p for p in problems), f"{expected!r} not in {problems}")


class HyperTest(unittest.TestCase):
    def test_csv_to_hyper_round_trip(self):
        try:
            from tableauhyperapi import Connection, HyperProcess, TableName, Telemetry
        except ImportError:
            self.skipTest("tableauhyperapi not installed")
        from arsenal.hyper_tools import csv_to_hyper

        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "sales.csv"
            csv.write_text("order_date,region,sales,returned\n2024-01-01,West,10.5,true\n2024-01-02,East,,false\n")
            hyper = csv_to_hyper(csv, parse_dates=["order_date"])
            with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
                with Connection(hp.endpoint, hyper) as conn:
                    rows = conn.execute_list_query(
                        f"SELECT region, sales FROM {TableName('Extract', 'Extract')} ORDER BY region")
        self.assertEqual(rows, [["East", None], ["West", 10.5]])


def _response(status=200, body=None, content=b""):
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(body).encode() if body is not None else content
    return resp


class FakeServer:
    """Records requests and answers like the Tableau REST API."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        path = url.split("/api/3.24", 1)[1]
        if path == "/auth/signin":
            return _response(body={"credentials": {"token": "tok", "site": {"id": "s1"}, "user": {"id": "u1"}}})
        if path == "/auth/signout":
            return _response(204)
        if path == "/sites/s1/projects":
            all_projects = [{"id": "p1", "name": "default"}, {"id": "p2", "name": "Portfolio"}]
            size, page = kwargs["params"]["pageSize"], kwargs["params"]["pageNumber"]
            projects = all_projects[(page - 1) * size: page * size]
            return _response(body={"pagination": {"totalAvailable": "2"}, "projects": {"project": projects}})
        if path == "/sites/s1/fileUploads" and method == "POST":
            return _response(body={"fileUpload": {"uploadSessionId": "up1"}})
        if path == "/sites/s1/fileUploads/up1":
            return _response(body={"fileUpload": {"uploadSessionId": "up1"}})
        if path == "/sites/s1/workbooks" and method == "POST":
            return _response(201, body={"workbook": {"id": "w1", "name": "kpi"}})
        if path == "/sites/s1/workbooks/w1/refresh":
            return _response(202, body={"job": {"id": "j1"}})
        return _response(404, content=b"not found")


class RestClientTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeServer()
        cfg = ServerConfig("https://tableau.example.com", "mysite", "pat", "secret", "3.24")
        self.ts = TableauServer(cfg)
        self.ts.session.request = self.fake
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_sign_in_sets_token_and_site(self):
        with self.ts as ts:
            self.assertEqual(ts.session.headers["X-Tableau-Auth"], "tok")
            self.assertEqual(ts.site_id, "s1")
        body = self.fake.calls[0][2]["json"]["credentials"]
        self.assertEqual(body["site"]["contentUrl"], "mysite")
        self.assertEqual(self.fake.calls[-1][1], "https://tableau.example.com/api/3.24/auth/signout")

    def test_projects_follow_pagination(self):
        self.ts.sign_in()
        names = [p["name"] for p in self.ts._paged(f"{self.ts.site_api}/projects", "projects", "project",
                                                   page_size=1)]
        self.assertEqual(names, ["default", "Portfolio"])
        self.assertEqual(len([c for c in self.fake.calls if c[1].endswith("/projects")]), 2)

    def test_single_request_publish(self):
        wb = Path(self.tmp.name) / "kpi.twbx"
        wb.write_bytes(b"PK-fake-twbx")
        self.ts.sign_in()
        result = self.ts.publish_workbook(wb, project="Portfolio", name='Q&A "KPI"')
        self.assertEqual(result["id"], "w1")

        method, url, kwargs = self.fake.calls[-1]
        self.assertEqual(kwargs["params"], {"overwrite": "true", "workbookType": "twbx"})
        self.assertTrue(kwargs["headers"]["Content-Type"].startswith("multipart/mixed; boundary="))
        body = kwargs["data"]
        self.assertIn(b'name="request_payload"', body)
        self.assertIn(b'name="tableau_workbook"; filename="kpi.twbx"', body)
        payload = body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0]
        workbook = ET.fromstring(payload).find("workbook")
        self.assertEqual(workbook.get("name"), 'Q&A "KPI"')  # escaped safely
        self.assertEqual(workbook.find("project").get("id"), "p2")
        self.assertIn(b"PK-fake-twbx", body)

    def test_chunked_publish(self):
        wb = Path(self.tmp.name) / "big.twbx"
        wb.write_bytes(b"x" * 25)
        self.ts.sign_in()
        with mock.patch.object(rest_client, "SINGLE_UPLOAD_LIMIT", 10), \
                mock.patch.object(rest_client, "CHUNK_SIZE", 10):
            self.ts.publish_workbook(wb, project="default")

        puts = [c for c in self.fake.calls if c[0] == "PUT"]
        self.assertEqual(len(puts), 3)  # 10 + 10 + 5 bytes
        method, url, kwargs = self.fake.calls[-1]
        self.assertEqual(kwargs["params"]["uploadSessionId"], "up1")
        self.assertNotIn(b"tableau_workbook", kwargs["data"])

    def test_errors_raise_with_status(self):
        self.ts.sign_in()
        with self.assertRaisesRegex(rest_client.TableauRestError, "404"):
            self.ts.views("missing")

    def test_refresh(self):
        self.ts.sign_in()
        self.assertEqual(self.ts.refresh_workbook("w1"), {"id": "j1"})


if __name__ == "__main__":
    unittest.main()
