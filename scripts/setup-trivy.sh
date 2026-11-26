#!/usr/bin/env bash
set -Eeuo pipefail
: "${RUNNER_TEMP:?Use only in an isolated CI runner}"
: "${GITHUB_PATH:?Use only in an isolated CI runner}"
image='docker.io/aquasec/trivy:0.76.2@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb'
docker pull "$image"
install -d "$RUNNER_TEMP/trivy-bin"
cid="$(docker create "$image")"
trap 'docker container rm "$cid" >/dev/null 2>&1 || true' EXIT
docker cp "$cid:/usr/local/bin/trivy" "$RUNNER_TEMP/trivy-bin/trivy"
chmod 0755 "$RUNNER_TEMP/trivy-bin/trivy"
"$RUNNER_TEMP/trivy-bin/trivy" --version | grep -Fx 'Version: 0.76.2'
printf '%s\n' "$RUNNER_TEMP/trivy-bin" >> "$GITHUB_PATH"
