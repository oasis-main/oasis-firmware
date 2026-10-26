#!/usr/bin/env bash
# FW-013 lint: every driver const in src/drivers/{sensors,actuators}.rs must be
# preceded by a "// STATUS:" line. Prints the placeholder backlog count.
# Allowed tags: placeholder | implemented, unvalidated | implemented, validated <date>
#               | <capability> confirmed unsupported per datasheet <section>
set -euo pipefail
cd "$(dirname "$0")/.."
rc=0
for f in src/drivers/sensors.rs src/drivers/actuators.rs; do
  awk -v F="$f" '
    /^\/\/ STATUS: / { tag=1; next }
    /^const [A-Z0-9_]+_DRIVER: &str/ { if (!tag) { printf "%s:%d: missing STATUS tag: %s\n", F, NR, $2; bad=1 } tag=0; next }
    { if ($0 !~ /^\/\//) tag=0 }
    END { exit bad }
  ' "$f" || rc=1
  printf '%s placeholder count: %s\n' "$f" "$(grep -c 'STATUS: placeholder' "$f" || true)"
done
exit $rc
