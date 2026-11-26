"""Offline fail-closed tests for promotion and GitHub repository setup."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


github = load("github_setup", "scripts/github_setup.py")
image = load("image_tests", "scripts/test-image.py")


def test_no_skipped_or_missing_ci_gate_allowed():
    jobs = [
        {"name": name, "status": "completed", "conclusion": "success"}
        for name in github.GATES
    ]
    github.verify_jobs(jobs)
    with pytest.raises(github.Stop):
        github.verify_jobs(jobs[:-1])
    with pytest.raises(github.Stop):
        github.verify_jobs(jobs, publish=True)
    jobs[0]["conclusion"] = "skipped"
    with pytest.raises(github.Stop):
        github.verify_jobs(jobs)


def test_rules_require_all_gates_and_reject_bypass():
    rule = github.rule_payload(15368)
    github.verify_rule(rule, 15368)
    rule["bypass_actors"] = [{"actor_id": 1}]
    with pytest.raises(github.Stop):
        github.verify_rule(rule, 15368)
    rule = github.rule_payload(15368)
    rule["rules"][-1]["parameters"]["required_status_checks"].pop()
    with pytest.raises(github.Stop):
        github.verify_rule(rule, 15368)


def test_zap_report_requires_successful_coverage_and_no_medium_high():
    report = {"site": [{"alerts": []}]}
    coverage = {"GET": 1, "POST": 1, "active_scan_completed": True}
    image.check_report(report, coverage)
    with pytest.raises(ValueError):
        image.check_report(report, {**coverage, "POST": 0})
    with pytest.raises(ValueError):
        image.check_report(report, {**coverage, "active_scan_completed": False})
    with pytest.raises(ValueError):
        image.check_report({"site": []}, coverage)
    report["site"][0]["alerts"].append({"riskcode": "2"})
    with pytest.raises(ValueError):
        image.check_report(report, coverage)


def test_security_boundary_contract():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    for name in github.GATES:
        assert f"name: {name}" in ci
    assert "pull_request_target:" not in ci
    assert "vars.PUBLISH_IMAGE == 'true'" in ci
    assert "persist-credentials: false" in ci
    assert "sbom: true" in ci and "provenance: mode=max" in ci
    assert '--tag "$NAME:sha-$GITHUB_SHA"' in ci
    compose = (ROOT / "compose.yaml").read_text()
    assert "127.0.0.1:18000:8000" in compose
    assert "read_only: true" in compose
    assert "docker.sock" not in compose
    assert "USER 10001:10001" in (ROOT / "Dockerfile").read_text()


def test_setup_does_not_protect_or_publish_after_failed_ci(monkeypatch):
    from types import SimpleNamespace

    repo = "owner/starter"
    sha = "a" * 40
    called = []

    def fake_api(path, method="GET", data=None):
        called.append((path, method))
        if path == f"repos/{repo}":
            return {
                "full_name": repo,
                "permissions": {"admin": True},
                "default_branch": "main",
            }
        if path.endswith("/actions/variables?per_page=100"):
            return {"variables": []}
        raise AssertionError(f"unexpected API call: {path}")

    def failed_dispatch(*args):
        raise github.Stop("CI failed")

    monkeypatch.setattr(github, "api", fake_api)
    monkeypatch.setattr(github, "main_sha", lambda repo: sha)
    monkeypatch.setattr(github, "dispatch_and_verify", failed_dispatch)
    args = SimpleNamespace(apply=True, publish_image=True, mark_template=True, wait=60)
    with pytest.raises(github.Stop, match="CI failed"):
        github.setup(repo, sha, args)
    assert all(method == "GET" for _, method in called)
