#!/usr/bin/env python3
"""Read fixed localhost lab APIs and verify scrape, dashboard and alert delivery."""

import argparse
import http.client
import json
import time
from urllib.parse import urlencode


def get(port, path):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} on lab port {port}")
        return json.loads(response.read(2_000_000))
    finally:
        connection.close()


def poll(label, predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                print(f"[PASS] {label}", flush=True)
                return
        except (OSError, RuntimeError, ValueError, KeyError, http.client.HTTPException):
            pass
        time.sleep(2)
    raise SystemExit(f"[FAIL] {label}: deadline reached")


def prom(expr):
    data = get(19090, "/api/v1/query?" + urlencode({"query": expr}))
    if data.get("status") != "success":
        raise RuntimeError("Prometheus query failed")
    return data["data"]["result"]


def scalar(expr):
    results = prom(expr)
    return float(results[0]["value"][1]) if len(results) == 1 else None


def workload_alert():
    return any(
        alert["labels"].get("alertname") == "WorkloadDown"
        and alert["status"]["state"] == "active"
        for alert in get(19093, "/api/v2/alerts")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["healthy", "metrics", "down", "recovered"])
    stage = parser.parse_args().stage
    if stage == "healthy":
        poll("Prometheus scrapes workload", lambda: scalar('up{job="workload"}') == 1)
        poll(
            "Grafana provisioned real dashboard",
            lambda: (
                get(13000, "/api/dashboards/uid/observability-overview")["dashboard"][
                    "uid"
                ]
                == "observability-overview"
            ),
        )
        poll("Alertmanager available", lambda: bool(get(19093, "/api/v2/status")))
    elif stage == "metrics":
        poll(
            "Prometheus ingested real request counter",
            lambda: (scalar('sum(obs_http_requests_total{status="2xx"})') or 0) >= 5,
        )
        poll(
            "Prometheus ingested 5xx counter",
            lambda: (scalar('sum(obs_http_requests_total{status="5xx"})') or 0) >= 5,
        )
        poll(
            "Prometheus ingested latency histogram",
            lambda: (scalar("sum(obs_http_request_duration_seconds_count)") or 0) >= 10,
        )
    elif stage == "down":
        poll("Prometheus sees failed scrape", lambda: scalar('up{job="workload"}') == 0)
        poll("Alertmanager received firing WorkloadDown", workload_alert)
    else:
        poll("Prometheus sees recovery", lambda: scalar('up{job="workload"}') == 1)
        poll("Alertmanager cleared WorkloadDown", lambda: not workload_alert())


if __name__ == "__main__":
    main()
