"""Rate-limited, read-only HTTP load smoke for one ForgeWorks service.

Safe defaults: 1 request/second for 30 seconds against public read endpoints.
Hard caps: max 5 rps, max 300 s, GET only, no redirects followed. An optional
bearer token (FW_LOAD_BEARER) is read from the environment and never printed.
This is NOT a capacity certification.

Usage:
  python3 scripts/load_smoke.py --base https://accessfix-ai-staging.up.railway.app [--rps 1] [--duration 30]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_BASE = "https://accessfix-ai-staging.up.railway.app"
# (path, expected statuses). Authenticated reads expect 401 without a token.
PATHS = [("/healthz", {200}), ("/readyz", {200}), ("/versionz", {200}), ("/v1/auth/config", {200}), ("/v1/scans/00000000-0000-0000-0000-000000000001/findings", {401, 403, 404})]
MAX_RPS = 5.0
MAX_DURATION = 300
TIMEOUT = 10


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = build_opener(_NoRedirect)


def one(base: str, path: str, token: str | None) -> tuple[str, int, float]:
    headers = {"Accept": "application/json", "User-Agent": "ForgeWorks-Load-Smoke/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    started = time.perf_counter()
    try:
        with _OPENER.open(Request(base + path, headers=headers, method="GET"), timeout=TIMEOUT) as r:
            r.read(4096)
            status = r.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        status = 0
    return path, status, (time.perf_counter() - started) * 1000


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1)], 1)


def validate(rps: float, duration: int) -> None:
    if not 0 < rps <= MAX_RPS:
        raise SystemExit(f"--rps must be in (0, {MAX_RPS}]")
    if not 0 < duration <= MAX_DURATION:
        raise SystemExit(f"--duration must be in (0, {MAX_DURATION}]")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--rps", type=float, default=1.0)
    ap.add_argument("--duration", type=int, default=30)
    args = ap.parse_args(argv)
    validate(args.rps, args.duration)
    if not args.base.startswith("https://"):
        raise SystemExit("--base must be https://")
    token = os.getenv("FW_LOAD_BEARER") or None
    results, lock, threads = [], threading.Lock(), []
    total = int(args.rps * args.duration)
    start = time.monotonic()
    for i in range(total):
        delay = start + i / args.rps - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        path, expected = PATHS[i % len(PATHS)]

        def run(path=path, expected=expected):
            res = one(args.base.rstrip("/"), path, token)
            with lock:
                results.append((*res, res[1] in expected))
        t = threading.Thread(target=run)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    report = {"base": args.base, "rps": args.rps, "duration_s": args.duration, "requests": len(results),
              "unexpected": sum(1 for r in results if not r[3]), "by_path": {}}
    for path, _ in PATHS:
        lat = [r[2] for r in results if r[0] == path]
        report["by_path"][path] = {"n": len(lat), "p50_ms": pct(lat, 50), "p95_ms": pct(lat, 95),
                                   "max_ms": round(max(lat), 1) if lat else 0,
                                   "statuses": sorted({r[1] for r in results if r[0] == path})}
    all_lat = [r[2] for r in results]
    report["overall"] = {"p50_ms": pct(all_lat, 50), "p95_ms": pct(all_lat, 95),
                         "mean_ms": round(statistics.fmean(all_lat), 1) if all_lat else 0}
    print(json.dumps(report, indent=2))
    return 1 if report["unexpected"] else 0


if __name__ == "__main__":
    sys.exit(main())
