# macOS — Docker Desktop (Intel / Apple silicon)

Install Git, Python 3.11+ and Docker Desktop for your supported macOS version and
CPU architecture. See https://docs.docker.com/desktop/setup/install/mac-install/.
Docker Desktop runs the Linux containers in its VM; the host does not need to
install Prometheus or Grafana manually.

In macOS Terminal, from the repository root:

```bash
docker context show
docker compose version
docker compose config --quiet
docker compose up -d --build
python3 scripts/integration-observability.py healthy
```

Open http://127.0.0.1:13000/d/observability-overview and follow the
[README](../README.md). The pinned images use multi-platform index references;
this does not prove full Apple silicon runtime compatibility. If the engine
cannot pull/run its architecture, use a dedicated Linux lab host rather than
changing the digests or disabling security. `docker compose stop` preserves
volumes.
