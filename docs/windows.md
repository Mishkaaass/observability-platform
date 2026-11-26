# Windows quickstart

Use Python 3.14 from python.org and Git for Windows, in PowerShell from the
cloned repository:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Open http://127.0.0.1:18000/. Stop with Ctrl+C. No global execution-policy
change is required. For container use, install Docker Desktop and enable
Linux containers. In PowerShell, `docker compose up --build` is an alternative.
For Bash tools and Linux-specific integrations use Ubuntu WSL 2; do not
install a second Docker daemon inside an integrated WSL environment. The
CI reference runtime is Linux; native Windows and each CPU are not yet tested.
