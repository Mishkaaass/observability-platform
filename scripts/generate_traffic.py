#!/usr/bin/env python3
"""Bounded traffic to the fixed local lab; no configurable host or port."""

import argparse
import http.client
import time

PATHS = {"healthy": "/api/status", "slow": "/lab/slow", "failure": "/lab/fail"}


def request(path: str) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", 18000, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        response.read(4096)
        return response.status
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=PATHS)
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.count <= 120:
        parser.error("count must be between 1 and 120")
    expected = 503 if args.mode == "failure" else 200
    for _ in range(args.count):
        if request(PATHS[args.mode]) != expected:
            raise SystemExit("Unexpected response; verify the local lab is running")
        time.sleep(0.2)
    print(f"[PASS] {args.count} local {args.mode} requests; HTTP {expected}")


if __name__ == "__main__":
    main()
