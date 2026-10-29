"""Rebuild generated data/charts in a clean temporary folder and compare bytes.

REPORT.md is human-reviewed; it is copied for image link checks, NOT regenerated.
This requires a local copy of the official KPX raw file (run analysis.py first).
"""
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import json
import hashlib

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="solar_reproduce_") as tmp:
    target = Path(tmp)
    for name in ["analysis.py", "insight_extension.py", "REPORT.md", "README.md", "requirements.txt"]:
        shutil.copy2(root / name, target / name)
    (target / "data").mkdir()
    shutil.copy2(root / "data/kpx_original.csv", target / "data/kpx_original.csv")
    shutil.copy2(root / "data/daily_weather_2025.csv", target / "data/daily_weather_2025.csv")
    subprocess.run([sys.executable, str(target / "analysis.py")],
                   cwd=tmp, capture_output=True, text=True, check=True)
    names = (
        [str(p.relative_to(root)) for p in sorted((root / "images").glob("*.png"))] +
        [str(p.relative_to(root)) for p in sorted((root / "images").glob("*.svg"))] +
        [str(p.relative_to(root)) for p in sorted((root / "data").glob("*"))
         if p.is_file() and p.name not in ["kpx_original.csv", "daily_weather_2025.csv", "reproducibility.json"]]
    )
    checks = {name: (root / name).read_bytes() == (target / name).read_bytes() for name in names}
    assert all(checks.values()), checks
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    assert "images/04_seasons.svg" in report and "images/05_cloud_weather.svg" in report
    result = {
        "clean_output_rebuild_passed": True,
        "files_identical": checks,
        "report_manually_authored_not_regenerated": True,
        "report_image_links_checked_by_analysis": True,
        "python_version": sys.version.split()[0],
        "input_sha256": hashlib.sha256((root / "data/kpx_original.csv").read_bytes()).hexdigest(),
        "environment_note": "Separate empty output directory in the same Python environment, not a different OS."
    }
    (root / "data/reproducibility.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
