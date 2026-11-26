#!/bin/sh
# Same release risk policy as OpsBoard. Scanner errors block the pipeline.
set -eu
[ "$#" -eq 1 ] && [ -n "$1" ] || { echo 'Usage: scan-image.sh IMAGE' >&2; exit 2; }
image="$1"
scan() {
    trivy image --scanners vuln --pkg-types os,library --no-progress "$@" "$image"
}
scan --severity HIGH,CRITICAL --ignore-unfixed=false --exit-code 0
scan --severity CRITICAL --ignore-unfixed=false --exit-code 1
scan --severity HIGH --ignore-unfixed=true --exit-code 1
