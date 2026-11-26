#!/usr/bin/env bash
# Mutations are restricted to a fresh project on a disposable GitHub CI runner.
set -Eeuo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]]
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ && "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]
export COMPOSE_PROJECT_NAME="obs-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
[[ -z "$(docker compose ps -aq)" ]] || { echo 'Existing lab; refusing cleanup'; exit 2; }
trap 'docker compose down -v --remove-orphans' EXIT
docker compose config --quiet
docker compose run --rm --no-deps --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose run --rm --no-deps --entrypoint /bin/promtool prometheus test rules /etc/prometheus/rules-test.yml
docker compose run --rm --no-deps --entrypoint /bin/amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
docker compose up -d --build
python3 scripts/integration-observability.py healthy
python3 scripts/generate_traffic.py healthy --count 12
python3 scripts/generate_traffic.py failure --count 12
python3 scripts/generate_traffic.py slow --count 6
python3 scripts/integration-observability.py metrics
docker compose stop starter
python3 scripts/integration-observability.py down
docker compose start starter
python3 scripts/integration-observability.py recovered
