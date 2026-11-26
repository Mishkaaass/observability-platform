# Reviewed image references (Phase 1)

The following official Docker Hub pages identify the multi-platform index digests
used by compose.yaml. A pinned digest makes image selection reproducible; it is not
proof of absence of vulnerabilities. The CI must actually pull and scan each image.

- Prometheus v3.16.0: https://hub.docker.com/layers/prom/prometheus/v3.16.0/images/sha256-89c1a644817e9ad70fa2af76c84898e327c1de7063735f962e8313b1e28672c3
- Alertmanager v0.35.1: https://hub.docker.com/layers/prom/alertmanager/v0.35.1/images/sha256-9c6c44a21180ab1aad3e3dd94a868ff0ac1870304414593d14bca5066eecf77d
- Grafana 13.2: https://hub.docker.com/layers/grafana/grafana/13.2/images/sha256-6a18782a9a4b67d468f98775c0e8ef6074c1f9f6e2556c3e21f15f326d4bcd79
- Workload Python base: the exact pinned digest and patch commands inherited from
  the tested DevSecOps Starter Template at commit 16936fcb2227c1f07b3479115c0696da7b120dce.

Official configuration references:
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- https://prometheus.io/docs/alerting/latest/alertmanager/
- https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/
- https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/anonymous-auth/
