# Reviewed image references — Phase 1

The exact references in compose.yaml are selected by immutable registry digest.
The original stable Prometheus v3.16.0, Alertmanager v0.35.1 and Grafana 13.2
images failed the new security gate. Their compiled Go dependencies included
golang.org/x/net before v0.62.0 (CVE-2026-78661); Grafana also had additional
fixable HIGH findings in bundled Go/plugin binaries.

The diagnostic CI run [45816618215](https://github.com/Mishkaaass/observability-platform/actions/runs/45816618215/job/139898368688)
resolved the following upstream registry tags to exact digests and independently
scanned all three with the same Trivy policy. Each candidate scan passed on
the GitHub-hosted Linux/amd64 runner. The candidates must still pass the complete
integration pipeline before merging. These are official registry repositories,
not locally patched binaries, and no vulnerability finding is ignored.

| Component | Exact selected image |
| --- | --- |
| Prometheus | `prom/prometheus:main@sha256:ebe85a42acf97bd460779d5a332c26461faedca7a94a6b46d12abfe2ad8f2f63` |
| Alertmanager | `prom/alertmanager:main@sha256:7bba3a8a156f4199240c231fbbe3b4bba6831e9adf07d4c111d9df4e558a1d5b` |
| Grafana | `grafana/grafana:13.2.7-slim@sha256:54d236dc16b4be398c730f7dc2898758318decca6acd99ddade32108a39013e0` |

Prometheus and Alertmanager are **development snapshots**, not stable releases.
The upstream stable releases available at the time of review (2026-11-26)
still used the vulnerable dependency. The `main` tag is never followed
dynamically: the OCI digest is the authority. This is a temporary educational
lab tradeoff; review upstream stable releases and replace the snapshots with
fixed stable images before representing the lab as a production-ready baseline.
Grafana is a patch release. Recheck all three on update; CI scans current
vulnerability databases, so a formerly green image may become blocked.

Upstream release pages:
- https://github.com/prometheus/prometheus/releases
- https://github.com/prometheus/alertmanager/releases
- https://github.com/grafana/grafana/releases

The workload uses the pinned Python base and patch commands inherited from the
verified DevSecOps Starter Template commit 16936fcb2227c1f07b3479115c0696da7b120dce.
CI validates Linux/amd64; other architectures and native OS runtime behavior
need separate verification. Digest pinning is not signature verification.

Official configuration references:
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- https://prometheus.io/docs/alerting/latest/alertmanager/
- https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/
- https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/anonymous-auth/
