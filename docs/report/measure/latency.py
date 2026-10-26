"""Latency of three request types through the public HTTPS address.

    uv run --no-project python docs/report/measure/latency.py > docs/report/data/latency.json
"""

import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = "https://hitc602.centralindia.cloudapp.azure.com"
N, WORKERS = 300, 10

req = urllib.request.Request(SITE + "/api/accounts/login?include_auth_token", method="POST",
                             data=json.dumps({"email": "asha@example.com", "password": "trekker123"}).encode(),
                             headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["response"]["user"]["authentication_token"]

targets = {
    "Front end page (Blob via ingress)": ("/treks", {}),
    "Health check (PostgreSQL query)": ("/api/health", {}),
    "Trek listing (Redis cache)": ("/api/treks", {"Authentication-Token": token}),
}


def timed(path, headers):
    r = urllib.request.Request(SITE + path, headers=headers)
    t = time.perf_counter()
    with urllib.request.urlopen(r, timeout=30) as resp:
        resp.read()
        code = resp.status
    return (time.perf_counter() - t) * 1000, code


out = {}
for name, (path, headers) in targets.items():
    timed(path, headers)  # warm the connection pool and the cache
    with ThreadPoolExecutor(WORKERS) as pool:
        samples = list(pool.map(lambda _: timed(path, headers), range(N)))
    ms = sorted(s[0] for s in samples)
    q = statistics.quantiles(ms, n=100)
    out[name] = {"n": N, "ok": sum(s[1] == 200 for s in samples),
                 "p50": round(q[49], 1), "p90": round(q[89], 1), "p99": round(q[98], 1),
                 "mean": round(statistics.mean(ms), 1)}
print(json.dumps(out, indent=2))
