# Security model

This is a disposable, single-machine education lab. Never point it at company or
production endpoints. The API is stateless and intentionally small; the published
image has the simulated incidents disabled unless explicitly enabled. The traffic
script has a fixed localhost target, capped request count, sequential requests and
bounded timeout. Metrics labels are a finite route/status set; structured workload
logs do not contain request bodies, query strings, auth headers or credentials.

The Docker images are digest-pinned to reviewed registry references. All exposed
ports bind to 127.0.0.1. There are no host Docker socket mounts, privileged
containers, host networks, or cloud credentials. The app and monitoring containers
run with dropped capabilities, non-root users, read-only root filesystems and
bounded memory/process counts. Named data volumes persist until explicitly removed.
This is not an air gap: Docker's local bridge can permit outbound access. Never
mount production data or connect the stack to a production network.

Grafana is a local anonymous Viewer, not an authenticated public dashboard. The
Prometheus/Alertmanager web APIs are local and not authentication-hardened; anyone
with access to the lab's host loopback can inspect or interact with them. Do not
forward ports to other machines. There is no external alert integration. The local
viewer is not a privilege boundary against administrators of the host or Docker.

## CI/CD

SHA-pinned actions, read-only CI permissions, Gitleaks, pip-audit, Ruff, Bandit,
Trivy, browser testing and isolated ZAP scans are inherited from the template.
ZAP tests the sample stateless JSON API on a disposable internal-network container,
not arbitrary endpoints or external services. Third-party monitoring images also
undergo Trivy scans: all CRITICAL and fixable HIGH findings block; unfixed HIGH
findings are reported and require review. Scanner errors block. A green check
proves only the stated policy, not absence of vulnerabilities. The current Prometheus and Alertmanager images are digest-pinned upstream development snapshots chosen because the stable versions failed the gate. This is a documented temporary lab choice, not a production approval; see [image review](docs/IMAGE_SOURCES.md). Dependabot proposes
updates; each must be reviewed. No unverified or skipped gate enables CD.

The CD job publishes only a candidate workload image, scans/smokes the exact
registry digest with the same policy, verifies current protected main, then tags
the approved digest. Buildx SBOM/provenance are attestations, not a signature or
production certification. There is no automatic deployment. Each repo needs its
own ruleset and publication opt-in; these settings are not inherited by copying
Git files.

No public release until real CI/CD and local demo evidence have been reviewed.
Report vulnerabilities privately to the repository owner; do not post credentials
or raw sensitive logs in issues.
