"""Pull Azure Monitor platform metrics for the test window into data/metrics.json.

    uv run --no-project python docs/report/measure/metrics.py

The window starts at the time in data/window-start.txt (written before the
tests) and ends now, at one-minute granularity.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RG = "hitc-rg"


def resource_id(kind, *args):
    return subprocess.run(["az", *kind, "-g", RG, *args, "--query", "id", "-o", "tsv"],
                          check=True, capture_output=True, text=True).stdout.strip()


def series(resource, metric, aggregation):
    start = (DATA / "window-start.txt").read_text().strip()
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = subprocess.run(["az", "monitor", "metrics", "list", "--resource", resource,
                          "--metric", metric, "--interval", "PT1M", "--aggregation", aggregation,
                          "--start-time", start, "--end-time", end, "-o", "json"],
                         check=True, capture_output=True, text=True).stdout
    points = json.loads(out)["value"][0]["timeseries"][0]["data"]
    key = aggregation.lower()
    t0 = datetime.fromisoformat(points[0]["timeStamp"])
    return [[(datetime.fromisoformat(p["timeStamp"]) - t0).total_seconds() / 60, p.get(key) or 0]
            for p in points]


aks = resource_id(["aks", "show"], "-n", "hitc-aks")
bus = resource_id(["servicebus", "namespace", "show"], "-n", "hitc602bus")
pg = resource_id(["postgres", "flexible-server", "show"], "-n", "hitc602-pg")

metrics = {
    "AKS node CPU (average across nodes)": {"unit": "percent", "points": series(aks, "node_cpu_usage_percentage", "Average")},
    "Service Bus messages received per minute": {"unit": "messages", "points": series(bus, "IncomingMessages", "Total")},
    "PostgreSQL CPU": {"unit": "percent", "points": series(pg, "cpu_percent", "Average")},
}
(DATA / "metrics.json").write_text(json.dumps(metrics, indent=1))
for name, s in metrics.items():
    print(f"{name}: {len(s['points'])} points, max {max(p[1] for p in s['points']):.1f}")
