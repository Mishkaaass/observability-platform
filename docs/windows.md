# Windows — Docker Desktop (Linux containers)

Install and start Docker Desktop on a supported Windows PC, using its WSL 2
backend and Linux containers. Install Git and Python 3.11+ for PowerShell, or use
Ubuntu WSL 2 with Docker Desktop integration enabled. Do not install a second
Docker daemon into WSL. Follow Microsoft's WSL installation guide if necessary:
https://learn.microsoft.com/en-us/windows/wsl/install.

In PowerShell in the repository root:

```powershell
docker context show
docker compose version
docker compose config --quiet
docker compose up -d --build
py -3 scripts/integration-observability.py healthy
py -3 scripts/generate_traffic.py healthy --count 30
```

If using Ubuntu WSL 2 instead, run the Linux commands with `python3`. Open
http://127.0.0.1:13000/d/observability-overview in the Windows browser. The
[README](../README.md) describes the outage drill. Use `docker compose stop`
to preserve the stack. No native Windows containers or public forwarding are
required. Full Windows runtime is pending independent verification.
