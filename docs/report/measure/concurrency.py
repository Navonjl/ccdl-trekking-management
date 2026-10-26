"""Fire concurrent bookings at the last free places of one trek.

Runs inside an API pod (stdin of `kubectl exec ... python -`), against the
internal trek-api service, so the ingress rate limit is not in the way and
the requests spread over every API replica. Prints one JSON object.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request

BASE = "http://trek-api"
SLOTS = 10
CLIENTS = 50
RUN = str(int(time.time()))


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authentication-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def login(email, password):
    status, body = call("POST", "/api/accounts/login?include_auth_token",
                        {"email": email, "password": password})
    return body["response"]["user"]["authentication_token"]


admin = login(os.environ.get("ADMIN_EMAIL", "admin@example.com"), os.environ["ADMIN_PASSWORD"])
status, trek = call("POST", "/api/admin/treks", {
    "name": f"Concurrency test {RUN}", "location": "Load test", "difficulty": "Easy",
    "status": "Open", "total_slots": SLOTS, "duration_days": 1, "price": 0,
}, admin)
trek_id = trek.get("id") or trek.get("trek", {}).get("id")

tokens = []
for n in range(CLIENTS):
    email = f"load{RUN}-{n}@example.com"
    call("POST", "/api/register", {"email": email, "password": "loadtest123",
                                   "full_name": f"Load {n}", "phone": f"9{n:09d}"})
    tokens.append(login(email, "loadtest123"))

barrier = threading.Barrier(CLIENTS)
results = [None] * CLIENTS


def book(i):
    barrier.wait()
    started = time.perf_counter()
    status, body = call("POST", "/api/bookings", {"trek_id": trek_id}, tokens[i])
    results[i] = {"status": status, "ms": round((time.perf_counter() - started) * 1000, 1),
                  "error": body.get("error")}


threads = [threading.Thread(target=book, args=(i,)) for i in range(CLIENTS)]
for t in threads:
    t.start()
for t in threads:
    t.join()

_, treks = call("GET", "/api/admin/treks", token=admin)
row = next(t for t in treks if t["id"] == trek_id)
print(json.dumps({
    "trek_id": trek_id, "slots": SLOTS, "clients": CLIENTS,
    "succeeded": sum(r["status"] == 201 for r in results),
    "rejected": sum(r["status"] != 201 for r in results),
    "errors": sorted({r["error"] for r in results if r["error"]}),
    "available_slots_after": row["available_slots"],
    "results": results,
}))
