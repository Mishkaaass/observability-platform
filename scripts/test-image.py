#!/usr/bin/env python3
"""Verify a fresh image, optionally scan its API in an internal Docker network.

No arbitrary URLs, published ports, host socket mounts or existing workloads.
Runs only on an explicitly selected, trusted local Docker engine.
"""

import argparse
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ZAP = (
    "docker.io/zaproxy/zap-stable@sha256:"
    "030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238"
)
SMOKE = r"""
import json,sys,urllib.request
base='http://starter:8000'
def get(path):
    with urllib.request.urlopen(base+path, timeout=5) as response:
        assert response.headers['X-Content-Type-Options']=='nosniff'
        return json.load(response)
assert get('/health')['status']=='ok'
assert get('/ready')['status']=='ready'
assert get('/version')['git_sha']==sys.argv[1]
assert get('/api/status')['status']=='ok'
request=urllib.request.Request(base+'/api/validate', data=b'{"message":"smoke"}',
                               headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request, timeout=5) as response:
    assert json.load(response)=={'accepted': True, 'length': 5}
print(json.dumps(get('/openapi.json')))
"""


def check_report(report, coverage):
    sites = report.get("site")
    if not isinstance(sites, list) or not sites:
        raise ValueError("missing ZAP site evidence")
    for site in sites:
        alerts = site.get("alerts")
        if not isinstance(alerts, list):
            raise ValueError("missing ZAP alert evidence")
        for alert in alerts:
            if int(alert["riskcode"]) >= 2:
                raise ValueError("ZAP reported a medium/high risk finding")
    for method in ("GET", "POST"):
        count = coverage.get(method)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("missing successful API coverage")
    if coverage.get("active_scan_completed") is not True:
        raise ValueError("active scan not complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("sha")
    parser.add_argument("--zap", action="store_true")
    args = parser.parse_args()
    containers = []
    network = None

    def docker(*command, timeout=120):
        return subprocess.run(
            ["docker", *command],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        ).stdout.strip()

    def create(*command):
        identifier = docker("create", *command)
        containers.append(identifier)
        return identifier

    try:
        if "@sha256:" in args.image:
            docker("pull", args.image, timeout=300)
        if args.zap:
            docker("pull", ZAP, timeout=300)
        name = "starter-" + uuid.uuid4().hex
        network = docker("network", "create", "--internal", name)
        app = create(
            "--network",
            network,
            "--network-alias",
            "starter",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=128",
            "--memory=512m",
            "--tmpfs",
            # Docker tmpfs, not a host file.
            "/tmp:rw,noexec,nosuid,size=16m",  # nosec B108
            args.image,
        )
        docker("start", app)
        for _ in range(45):
            try:
                spec = json.loads(docker("exec", app, "python", "-c", SMOKE, args.sha))
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise RuntimeError("image health, version or API contract failed")
        if not args.zap:
            print("PASS: disposable image contract")
            return 0
        paths = spec["paths"]
        spec["paths"] = {k: v for k, v in paths.items() if k.startswith("/api/")}
        if not spec["paths"]:
            raise ValueError("no API paths selected")
        spec["servers"] = [{"url": "http://starter:8000"}]
        with tempfile.TemporaryDirectory(prefix="starter-zap-") as temporary:
            directory = Path(temporary)
            (directory / "api.json").write_text(json.dumps(spec))
            (directory / "hook.py").write_text(
                Path(__file__).with_name("zap-coverage-hook.py").read_text()
            )
            # Stateless, cookie-free POST has no CSRF-sensitive action.
            # Remove this exception when adding authenticated cookie-based APIs.
            rules = "10202\tIGNORE\tStateless JSON validation\n"
            (directory / "rules.conf").write_text(rules)
            mounts = []
            for name in ("api.json", "hook.py", "rules.conf"):
                source = directory / name
                source.chmod(0o644)
                mounts.extend(
                    ["--mount", f"type=bind,src={source},dst=/zap/{name},readonly"]
                )
            config = (
                "-config ascan.maxScanDurationInMins=0 "
                "-config ascan.maxRuleDurationInMins=0"
            )
            scanner = create(
                "--network",
                network,
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                *mounts,
                ZAP,
                "sh",
                "-c",
                'mkdir -p /zap/wrk && exec zap-api-scan.py "$@"',
                "zap-scan",
                "-t",
                "/zap/api.json",
                "-f",
                "openapi",
                "-c",
                "/zap/rules.conf",
                "-J",
                "report.json",
                "--hook",
                "/zap/hook.py",
                "-T",
                "10",
                "-z",
                config,
            )
            result = subprocess.run(
                ["docker", "start", "-a", scanner],
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            if result.returncode not in (0, 1, 2):
                raise RuntimeError("ZAP execution failed")
            for name in ("report.json", "coverage.json"):
                docker("cp", f"{scanner}:/zap/wrk/{name}", str(directory / name))
            report = json.loads((directory / "report.json").read_text())
            coverage = json.loads((directory / "coverage.json").read_text())
            # Save counts only, not raw requests or responses.
            destination = Path("artifacts/security")
            destination.mkdir(parents=True, exist_ok=True)
            alerts = [
                {"rule_id": str(a.get("pluginid", "")), "risk": int(a["riskcode"])}
                for site in report.get("site", [])
                for a in site.get("alerts", [])
            ]
            summary = {"coverage": coverage, "alerts": alerts}
            (destination / "zap-summary.json").write_text(json.dumps(summary, indent=2))
            check_report(report, coverage)
        print("PASS: isolated ZAP API scan and verified GET/POST coverage")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: image verification ({type(exc).__name__}); no promotion allowed")
        return 1
    finally:
        for container in reversed(containers):
            subprocess.run(
                ["docker", "rm", "-f", container],
                check=False,
                capture_output=True,
                timeout=30,
            )
        if network:
            subprocess.run(
                ["docker", "network", "rm", network],
                check=False,
                capture_output=True,
                timeout=30,
            )


if __name__ == "__main__":
    raise SystemExit(main())
