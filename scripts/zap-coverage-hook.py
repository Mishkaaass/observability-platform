"""Record real successful GET/POST coverage and completed active scanning."""

import json
from pathlib import Path
from urllib.parse import urlsplit


def zap_pre_shutdown(zap):
    covered = {"GET": 0, "POST": 0}
    messages = zap.core.messages(baseurl="http://starter:8000", start=0, count=10000)
    for message in messages:
        lines = message.get("requestHeader", "").splitlines()
        response = message.get("responseHeader", "").splitlines()
        if not lines or not response:
            continue
        request = lines[0].split()
        status = response[0].split()
        if len(request) < 2 or len(status) < 2:
            continue
        method, target = request[:2]
        parsed = urlsplit(target)
        if parsed.netloc and parsed.netloc != "starter:8000":
            continue
        if parsed.path.startswith("/api/") and method in covered:
            if status[1].startswith("2"):
                covered[method] += 1
    scans = zap.ascan.scans
    covered["active_scan_completed"] = (
        bool(scans)
        and all(str(scan.get("progress")) == "100" for scan in scans)
        and len(messages) < 10000
    )
    Path("/zap/wrk/coverage.json").write_text(json.dumps(covered))
