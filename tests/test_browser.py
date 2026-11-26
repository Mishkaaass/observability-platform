"""Real Chromium on a disposable loopback service; never scans a remote URL."""

import os
import socket
import threading
import time

import pytest
import uvicorn

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BROWSER_SECURITY") != "1", reason="explicit Chromium test job"
)


def test_browser_headers_and_cross_origin():
    from playwright.sync_api import expect, sync_playwright

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    response = page.goto(f"http://127.0.0.1:{port}/")
                    assert response is not None and response.status == 200
                    expect(page.get_by_role("heading")).to_have_text("Observability Platform ready")
                    assert response.headers["x-frame-options"] == "DENY"
                    csp = response.headers["content-security-policy"]
                    assert "default-src 'none'" in csp
                    stored = page.evaluate(
                        "localStorage.length + sessionStorage.length"
                    )
                    assert stored == 0
                    assert page.context.cookies() == []
                finally:
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()
