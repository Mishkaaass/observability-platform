#!/usr/bin/env python3
"""Set up a new template-derived repo only after verifying real GitHub Actions.

Dry-run by default. No changes to OpsBoard or Terraform AWS Lab. Existing
rulesets are preserved; conflicting rules or a moving main cause a safe stop.
"""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

GATES = (
    "Code quality",
    "Python tests",
    "Dependency security",
    "Secret security",
    "Container security",
    "API and browser security",
    "Isolated API attack scan",
)
RULE_NAME = "devsecops-main-quality-gates"
PUBLISH = "Publish Docker image"
ACTIONS_APP_ID = 15368
ENV = {
    **os.environ,
    "GH_HOST": "github.com",
    "GH_PAGER": "cat",
    "GH_PROMPT_DISABLED": "1",
}
ROOT = Path(__file__).resolve().parents[1]


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def command(*args, payload=None):
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        env=ENV,
        input=payload,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode:
        status = re.search(r"HTTP \d{3}\b", result.stderr)
        detail = status.group() if status else "command error"
        raise Stop(f"{args[0]} failed ({detail}); inspect local permissions")
    return result.stdout.strip()


def api(path, method="GET", data=None):
    args = ["gh", "api", "--hostname", "github.com", "--method", method, path]
    if data is not None:
        args += ["--input", "-"]
    result = command(*args, payload=json.dumps(data) if data is not None else None)
    return json.loads(result) if result else None


def main_sha(repo):
    return api(f"repos/{repo}/branches/main")["commit"]["sha"]


def rule_payload(app_id):
    return {
        "name": RULE_NAME,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True,
                    "allowed_merge_methods": ["squash", "merge", "rebase"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {"context": name, "integration_id": app_id} for name in GATES
                    ],
                },
            },
        ],
    }


def verify_rule(rule, app_id):
    require(rule.get("enforcement") == "active", "ruleset is not active")
    require(rule.get("target") == "branch", "ruleset target differs")
    require(not rule.get("bypass_actors"), "ruleset permits bypass")
    ref = rule.get("conditions", {}).get("ref_name", {})
    require(ref.get("include") == ["refs/heads/main"], "ruleset scope differs")
    require(not ref.get("exclude"), "ruleset excludes a branch")
    rules = {r["type"]: r.get("parameters", {}) for r in rule.get("rules", [])}
    require(
        {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
        <= rules.keys(),
        "ruleset lacks safety rules",
    )
    require(
        rules["pull_request"].get("required_review_thread_resolution") is True,
        "review thread resolution not required",
    )
    checks = rules["required_status_checks"]
    require(checks.get("strict_required_status_checks_policy") is True, "not strict")
    observed = {
        (item["context"], item.get("integration_id"))
        for item in checks.get("required_status_checks", [])
    }
    require({(name, app_id) for name in GATES} <= observed, "missing required checks")


def verify_jobs(jobs, publish=False):
    names = GATES + ((PUBLISH,) if publish else ())
    for name in names:
        matching = [job for job in jobs if job.get("name") == name]
        require(len(matching) == 1, f"missing or ambiguous job: {name}")
        require(
            matching[0].get("status") == "completed"
            and matching[0].get("conclusion") == "success",
            f"job did not pass: {name}",
        )


def dispatch_and_verify(repo, sha, publish, wait):
    path = (
        f"repos/{repo}/actions/workflows/ci.yml/runs?event=workflow_dispatch"
        f"&branch=main&head_sha={sha}&per_page=100"
    )
    deadline = time.monotonic() + min(wait, 180)
    while True:
        workflows = api(f"repos/{repo}/actions/workflows?per_page=100")
        active = any(
            item.get("path") == ".github/workflows/ci.yml"
            and item.get("state") == "active"
            for item in workflows.get("workflows", [])
        )
        if active:
            break
        require(time.monotonic() < deadline, "CI workflow is not active")
        time.sleep(10)
    before = {run["id"] for run in api(path)["workflow_runs"]}
    require(main_sha(repo) == sha, "main moved before dispatch")
    command("gh", "workflow", "run", "ci.yml", "--ref", "main", "--repo", repo)
    deadline = time.monotonic() + wait
    run_id = None
    while time.monotonic() < deadline:
        require(main_sha(repo) == sha, "main moved during verification")
        if run_id is None:
            found = [
                run
                for run in api(path)["workflow_runs"]
                if run["id"] not in before and run["head_sha"] == sha
            ]
            require(len(found) <= 1, "ambiguous new workflow run")
            if found:
                run_id = found[0]["id"]
                print(
                    f"[RUN] https://github.com/{repo}/actions/runs/{run_id}",
                    flush=True,
                )
        if run_id is not None:
            run = api(f"repos/{repo}/actions/runs/{run_id}")
            require(run["head_sha"] == sha, "wrong workflow revision")
            if run["status"] == "completed":
                require(run["conclusion"] == "success", f"run {run_id} did not pass")
                result = api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
                verify_jobs(result["jobs"], publish)
                print(f"[PASS] all required jobs at {sha[:12]}", flush=True)
                return
        print("[WAIT] GitHub Actions", flush=True)
        time.sleep(20)
    raise Stop("workflow verification deadline reached; no further setup performed")


def github_actions_app(repo, sha):
    result = api(f"repos/{repo}/commits/{sha}/check-runs?filter=latest&per_page=100")
    runs = result.get("check_runs", [])
    ids = set()
    for name in GATES:
        matches = [
            run
            for run in runs
            if run.get("name") == name
            and run.get("head_sha") == sha
            and run.get("app", {}).get("slug") == "github-actions"
            and run.get("conclusion") == "success"
        ]
        require(bool(matches), f"no successful GitHub Actions check: {name}")
        ids.update(run["app"]["id"] for run in matches)
    require(len(ids) == 1, "ambiguous GitHub Actions app identity")
    app_id = ids.pop()
    require(app_id == ACTIONS_APP_ID, "unexpected GitHub Actions application ID")
    return app_id


def stable_release(repo, sha):
    tag = "v1.0.0"
    releases = api(f"repos/{repo}/releases?per_page=100")
    existing = [release for release in releases if release["tag_name"] == tag]
    require(len(existing) <= 1, "ambiguous starter release")
    require(main_sha(repo) == sha, "main moved before release")
    if not existing:
        # Never move an existing tag. The initial tag is created by gh release.
        tags = api(f"repos/{repo}/tags?per_page=100")
        matches = [item for item in tags if item["name"] == tag]
        require(not matches or matches[0]["commit"]["sha"] == sha, "tag conflict")
        command(
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--target",
            sha,
            "--title",
            "DevSecOps Starter v1.0.0",
            "--notes",
            "Verified seven CI gates, protected main, and digest-verified CD.",
        )
    release = api(f"repos/{repo}/releases/tags/{tag}")
    require(not release["draft"] and not release["prerelease"], "not stable")
    tags = api(f"repos/{repo}/tags?per_page=100")
    matches = [item for item in tags if item["name"] == tag]
    require(
        len(matches) == 1 and matches[0]["commit"]["sha"] == sha,
        "release mismatch",
    )
    print(f"[PASS] stable release: {release['html_url']}", flush=True)


def setup(repo, sha, args):
    data = api(f"repos/{repo}")
    require(data["full_name"].lower() == repo.lower(), "repository mismatch")
    require(data.get("permissions", {}).get("admin"), "administrator required")
    require(data.get("default_branch") == "main", "main must be default")
    require(not data.get("archived"), "repository is archived")
    require(main_sha(repo) == sha, "local main differs from GitHub main")
    variables = api(f"repos/{repo}/actions/variables?per_page=100")
    publishing = any(
        item["name"] == "PUBLISH_IMAGE" and item["value"] == "true"
        for item in variables.get("variables", [])
    )
    if publishing:
        require(api(f"repos/{repo}/branches/main")["protected"], "unprotected main")
        existing = api(f"repos/{repo}/rulesets?per_page=100")
        managed = [item for item in existing if item["name"] == RULE_NAME]
        require(len(managed) == 1, "publishing requires the managed ruleset")
        rule_id = managed[0]["id"]
        verify_rule(api(f"repos/{repo}/rulesets/{rule_id}"), ACTIONS_APP_ID)
    if not args.apply:
        print(f"[PLAN] {repo} {sha[:12]}: CI -> strict main rules -> optional CD")
        return
    dispatch_and_verify(repo, sha, publishing, args.wait)
    app_id = github_actions_app(repo, sha)
    require(main_sha(repo) == sha, "main moved before applying protection")
    rules = api(f"repos/{repo}/rulesets?per_page=100")
    matches = [item for item in rules if item["name"] == RULE_NAME]
    require(len(matches) <= 1, "duplicate managed rulesets")
    if matches:
        rule_id = matches[0]["id"]
    else:
        rule_id = api(f"repos/{repo}/rulesets", "POST", rule_payload(app_id))["id"]
    verify_rule(api(f"repos/{repo}/rulesets/{rule_id}"), app_id)
    require(api(f"repos/{repo}/branches/main")["protected"], "main not protected")
    print(f"[PASS] strict main ruleset {rule_id}; existing rules preserved", flush=True)
    if args.publish_image and not publishing:
        require(main_sha(repo) == sha, "main moved before publication")
        command(
            "gh", "variable", "set", "PUBLISH_IMAGE", "--body", "true", "--repo", repo
        )
        dispatch_and_verify(repo, sha, True, args.wait)
        publishing = True
    if args.mark_template:
        require(repo.split("/")[1] == "devops-starter-template", "wrong template name")
        require(publishing, "template publication must pass before marking as template")
        require(main_sha(repo) == sha, "main moved before template setup")
        stable_release(repo, sha)
        api(f"repos/{repo}", "PATCH", {"is_template": True})
        require(
            api(f"repos/{repo}").get("is_template") is True, "template flag not set"
        )
        print(f"[PASS] https://github.com/{repo} is a GitHub template", flush=True)
    require(main_sha(repo) == sha, "main moved after setup")
    print(f"[PASS] {repo}: verified CI and main protection", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--publish-image", action="store_true")
    parser.add_argument("--mark-template", action="store_true")
    parser.add_argument("--wait", type=int, default=3600)
    args = parser.parse_args()
    require(60 <= args.wait <= 7200, "--wait must be 60 to 7200 seconds")
    require(not args.mark_template or args.publish_image, "template requires CD proof")
    require(command("git", "branch", "--show-current") == "main", "checkout main first")
    require(not command("git", "status", "--porcelain"), "dirty checkout; stop")
    origin = command("git", "remote", "get-url", "origin")
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/]+)", origin
    )
    require(match is not None, "origin is not a simple GitHub URL")
    owner, name = match.groups()
    name = name.removesuffix(".git")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", name) is not None, "invalid repo name")
    require(
        name.lower() not in {"ci-cd-lab", "terraform-aws-lab"},
        "existing lab is out of scope",
    )
    require(
        api("user")["login"].lower() == owner.lower(), "not your personal repository"
    )
    require(
        not args.mark_template or name == "devops-starter-template",
        "wrong template name",
    )
    setup(f"{owner}/{name}", command("git", "rev-parse", "HEAD"), args)


if __name__ == "__main__":
    try:
        main()
    except (Stop, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        print(f"[STOP] {error}", flush=True)
        raise SystemExit(1) from None
