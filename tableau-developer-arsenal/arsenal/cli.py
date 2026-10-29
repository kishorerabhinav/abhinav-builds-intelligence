"""Command line entry point: `tda <group> <command>`."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _print(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _write_csv(rows: list[dict], dest: str) -> None:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {dest}")


# -- tableau public ------------------------------------------------------

def cmd_public(args) -> None:
    from .config import public_user
    from .public_api import TableauPublic

    tp = TableauPublic()
    user = public_user(args.user)
    if args.action == "profile":
        _print(tp.profile(user))
    elif args.action == "stats":
        rows = tp.stats(user, details=args.details)
        if args.csv:
            _write_csv(rows, args.csv)
        else:
            for r in rows:
                print(f"{r['views']:>8}  {r['favorites']:>4}  {r['title']}")
    elif args.action == "image":
        if not args.workbook:
            raise SystemExit("image needs --workbook (and optionally --view)")
        dest = Path(args.out or f"out/{args.workbook}_{args.view or 'default'}.png")
        print(tp.view_image(args.workbook, args.view, dest))


def cmd_publish_public(args) -> None:
    from .public_publish import open_for_publish

    open_for_publish(args.workbook)


# -- tableau server / cloud ---------------------------------------------

def cmd_server(args) -> None:
    from .config import ServerConfig
    from .rest_client import TableauServer

    with TableauServer(ServerConfig.from_env()) as ts:
        a = args.action
        if a == "whoami":
            _print({"server": ts.config.server_url, "site_id": ts.site_id, "user_id": ts.user_id})
        elif a == "projects":
            for p in ts.projects():
                print(f"{p['id']}  {p['name']}")
        elif a == "workbooks":
            for w in ts.workbooks():
                print(f"{w['id']}  {w.get('project', {}).get('name', ''):<25} {w['name']}")
        elif a == "views":
            for v in ts.views(ts.find_workbook(args.name)["id"]):
                print(f"{v['id']}  {v['name']}")
        elif a == "publish":
            path = Path(args.file)
            if path.suffix.lower() in (".tds", ".tdsx", ".hyper"):
                result = ts.publish_datasource(path, args.project, args.name, not args.no_overwrite)
            else:
                result = ts.publish_workbook(path, args.project, args.name, not args.no_overwrite, args.show_tabs)
            _print(result)
        elif a == "download":
            wb = ts.find_workbook(args.name)
            print(ts.download_workbook(wb["id"], args.out or f"out/{args.name}.twbx", not args.no_extract))
        elif a == "refresh":
            _print(ts.refresh_workbook(ts.find_workbook(args.name)["id"]))
        elif a == "export":
            wb = ts.find_workbook(args.name)
            view = next((v for v in ts.views(wb["id"]) if v["name"] == args.view), None)
            if not view:
                raise SystemExit(f"View not found: {args.view}")
            filters = dict(f.split("=", 1) for f in args.filter or [])
            print(ts.export_view(view["id"], args.out or f"out/{args.view}.{args.format}", args.format, **filters))


# -- local files ---------------------------------------------------------

def cmd_twb(args) -> None:
    from . import workbook_tools as wt

    if args.action == "inspect":
        _print(wt.inspect_workbook(args.file))
    elif args.action == "lint":
        paths = wt.find_hardcoded_paths(args.file)
        if paths:
            print("Absolute paths in connections (package as .twbx or repoint before sharing):")
            for p in paths:
                print(f"  {p}")
            sys.exit(1)
        print("No hard-coded file paths found.")
    elif args.action == "package":
        print(wt.package_twbx(args.file, args.data or [], args.out))


def cmd_hyper(args) -> None:
    from .hyper_tools import csv_to_hyper

    print(csv_to_hyper(args.csv, args.out, args.parse_dates))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tda", description="Tableau Developer Arsenal")
    sub = p.add_subparsers(dest="group", required=True)

    pub = sub.add_parser("public", help="Read Tableau Public profile data")
    pub.add_argument("action", choices=["profile", "stats", "image"])
    pub.add_argument("--user", help="Profile name (default: TABLEAU_PUBLIC_USER)")
    pub.add_argument("--csv", help="stats: write rows to this CSV")
    pub.add_argument("--details", action="store_true", help="stats: add publish dates and size")
    pub.add_argument("--workbook", help="image: workbook repo URL")
    pub.add_argument("--view", help="image: view repo URL (default view if omitted)")
    pub.add_argument("--out")
    pub.set_defaults(func=cmd_public)

    pp = sub.add_parser("publish-public", help="Open a workbook in Tableau Public Desktop to publish")
    pp.add_argument("workbook")
    pp.set_defaults(func=cmd_publish_public)

    srv = sub.add_parser("server", help="Tableau Server / Cloud via REST API")
    srv.add_argument("action", choices=["whoami", "projects", "workbooks", "views", "publish",
                                        "download", "refresh", "export"])
    srv.add_argument("--file", help="publish: .twb/.twbx/.tds/.tdsx/.hyper")
    srv.add_argument("--project", default="default")
    srv.add_argument("--name", help="Workbook name (publish defaults to file name)")
    srv.add_argument("--view", help="export: view name")
    srv.add_argument("--format", choices=["png", "pdf", "csv"], default="png")
    srv.add_argument("--filter", action="append", help="export: Field=Value (repeatable)")
    srv.add_argument("--out")
    srv.add_argument("--no-overwrite", action="store_true")
    srv.add_argument("--show-tabs", action="store_true")
    srv.add_argument("--no-extract", action="store_true")
    srv.set_defaults(func=cmd_server)

    twb = sub.add_parser("twb", help="Inspect, lint or package local workbooks")
    twb.add_argument("action", choices=["inspect", "lint", "package"])
    twb.add_argument("file")
    twb.add_argument("--data", nargs="*", help="package: data files to bundle")
    twb.add_argument("--out")
    twb.set_defaults(func=cmd_twb)

    hy = sub.add_parser("hyper", help="Convert CSV to a .hyper extract")
    hy.add_argument("csv")
    hy.add_argument("--out")
    hy.add_argument("--parse-dates", nargs="*")
    hy.set_defaults(func=cmd_hyper)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
