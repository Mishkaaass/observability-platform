# Linux — local observability lab

Install Git, Python 3.11+ and Docker Engine with Compose v2 from trusted sources.
For an Ubuntu/Debian system, Git and Python are available from the normal package
manager; install Docker using https://docs.docker.com/engine/install/. Use a
non-root user with authorized access to a dedicated local Docker daemon. Docker
daemon access is a privileged capability; never chmod the Docker socket to 666.

In the repository root:

```bash
docker context show
docker compose version
docker compose config --quiet
docker compose up -d --build
python3 scripts/integration-observability.py healthy
```

Open http://127.0.0.1:13000/d/observability-overview in a local browser. See the
[README](../README.md) for traffic and outage drills. Stop using `docker compose
stop` to preserve data. No host pip packages are required to generate traffic.
