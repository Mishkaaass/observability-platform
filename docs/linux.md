# Linux quickstart

Install Git and Python 3.14 with venv from a trusted source. Use a non-root
user. From the cloned project:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Open http://127.0.0.1:18000/. Stop with Ctrl+C. Never use sudo pip or replace
system Python. Alternatively install Docker Engine / Compose v2 from the
official vendor, then run `docker compose up --build` on a trusted local
Docker daemon. Use one route at a time. No AWS account is needed.
