# Security model

This is a starter lab, not a production security certification. Never expose
its sample HTTP server to the internet. Report suspected vulnerabilities
privately to the repository owner using GitHub's private reporting mechanism
if enabled; do not include credentials, customer data or raw scan traffic.

- Loopback-only local service; non-root container, read-only filesystem, no
  Docker socket, no cloud credentials, no host mounts in the application.
- Pull request CI uses read permissions. Publishing is opt-in, only after all
  required jobs pass on main. The published candidate is scanned and exercised
  by exact digest before receiving a verified `sha-...` tag. Failed candidate
  tags can remain in GHCR and must not be deployed. A tag can be mutable; deploy
  by the recorded digest, not a tag.
- Trivy blocks all CRITICAL findings and fixable HIGH findings. Unfixed HIGH
  findings are reported and require explicit review; scanner errors block CI.
- Action and base-image digests use the reviewed OpsBoard baseline. Top-level
  Python versions are pinned; transitive dependencies and apt security updates
  are not a full reproducible lock. Review new findings and dependency updates.
- ZAP scans a new disposable container in a private internal Docker network;
  never give it a production URL. The stateless JSON sample has no cookie auth
  or persistent mutations. The anti-CSRF exception is limited to that sample;
  remove it and implement real role/CSRF tests when introducing credentials.
- Only sanitized finding IDs, risk codes and coverage counts are uploaded.
- Rulesets require PRs, seven named checks from GitHub Actions, up-to-date main,
  no force pushes/deletion and no bypass. Zero human approvals are configured
  for a solo portfolio; require human review for a real team.
- CD does not deploy to AWS or Kubernetes. GHCR package visibility is a
  separate GitHub setting. No custom repository secrets are needed.
