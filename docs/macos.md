# macOS quickstart

Install Git (Apple command-line tools) and Python 3.14 from python.org or
an existing trusted Homebrew installation. From macOS Terminal:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Open http://127.0.0.1:18000/. Stop with Ctrl+C. For the container route install
Docker Desktop for your Intel or Apple silicon architecture and run
`docker compose up --build` on its local engine. Use one route at a time.
The Linux CI reference image is tested on amd64; native macOS and all ARM
combinations require independent validation. Use a Linux VM if necessary.
