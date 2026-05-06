#!/usr/bin/env bash
# Mac double-click launcher.
# Drop this file in Finder and double-click it; macOS opens Terminal and runs launch.sh.
# Same as `./launch.sh` from a terminal. All flags pass through.

cd "$(dirname "$0")"
exec bash ./launch.sh "$@"
