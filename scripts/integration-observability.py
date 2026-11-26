#!/usr/bin/env python3
"""Verify real metrics, log ingestion, dashboard and local alert delivery."""

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


def log_events(expr):
    end = time.time_ns()
    path = "/api/datasources/proxy/uid/workload-loki/loki/api/v1/query_range?"
    params = {"query": expr, "start": end - 120_000_000_000, "end": end, "limit": 200}
    data = get(13000, path + urlencode(params))
    if data.get("status") != "success" or data["data"]["resultType"] != "streams":
        raise RuntimeError("Loki query failed")
    return [
        json.loads(line)
        for stream in data["data"]["result"]
        for _, line in stream["values"]
    ]


def matching_log(route, status, minimum_ms=0):
    return any(
        event.get("event") == "workload_request"
        and event.get("route") == route
        and event.get("status") == status
        and event.get("duration_ms", -1) >= minimum_ms
        and event.get("timestamp")
        for event in log_events('{service="workload"} | json')
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=["healthy", "metrics", "logs", "down", "recovered"]
    )
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
    elif stage == "logs":
        poll(
            "Grafana provisioned the Loki dashboard",
            lambda: get(13000, "/api/dashboards/uid/observability-logs")["dashboard"][
                "uid"
            ]
            == "observability-logs",
        )
        poll(
            "Real HTTP 200 log reached Loki through Alloy and Grafana",
            lambda: matching_log("/api/status", 200),
            timeout=180,
        )
        poll(
            "Real HTTP 503 log reached Loki",
            lambda: matching_log("/lab/fail", 503),
        )
        poll(
            "Real slow request log includes measured latency",
            lambda: matching_log("/lab/slow", 200, minimum_ms=300),
        )
    elif stage == "down":
        poll("Prometheus sees failed scrape", lambda: scalar('up{job="workload"}') == 0)
        poll("Alertmanager received firing WorkloadDown", workload_alert)
    else:
        poll("Prometheus sees recovery", lambda: scalar('up{job="workload"}') == 1)
        poll("Alertmanager cleared WorkloadDown", lambda: not workload_alert())


if __name__ == "__main__":
    main()
