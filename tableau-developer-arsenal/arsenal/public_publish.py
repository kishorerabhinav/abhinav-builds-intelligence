"""Hand a workbook to Tableau Public Desktop for publishing.

Tableau Public has no publishing API: workbooks reach a Public profile only
through the desktop app's File > Save to Tableau Public. This opens the file in
that app so the last step is one click and a sign-in.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS_GLOBS = [
    r"C:\Program Files\Tableau\Tableau Public*\bin\tabpublic.exe",
    r"C:\Program Files\Tableau\Tableau Public*\bin\tableau*.exe",
]


def find_tableau_public() -> str | None:
    if os.environ.get("TABLEAU_PUBLIC_EXE"):
        return os.environ["TABLEAU_PUBLIC_EXE"]
    if sys.platform == "win32":
        hits = sorted(h for pattern in WINDOWS_GLOBS for h in glob.glob(pattern))
        return hits[-1] if hits else None
    if sys.platform == "darwin":
        apps = sorted(glob.glob("/Applications/Tableau Public*.app"))
        return apps[-1] if apps else None
    return shutil.which("tableau-public")


def open_for_publish(workbook: str | Path) -> None:
    workbook = Path(workbook).resolve()
    exe = find_tableau_public()
    if not exe:
        raise SystemExit(
            "Tableau Public Desktop not found. Install it from https://public.tableau.com/app/discover "
            "or set TABLEAU_PUBLIC_EXE."
        )
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", exe, str(workbook)])
    else:
        subprocess.Popen([exe, str(workbook)])
    print(f"Opened {workbook.name} in Tableau Public. Use File > Save to Tableau Public to publish.")
