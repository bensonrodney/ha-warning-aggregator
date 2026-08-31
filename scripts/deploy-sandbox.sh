#!/usr/bin/env bash
# Deploy the in-development integration into the local sandbox Home Assistant
# container and restart it so the new code is loaded.
#
# Usage: scripts/deploy-sandbox.sh
set -euo pipefail

CONTAINER="${HA_CONTAINER:-homeassistant}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/custom_components/warning_aggregator"

echo ">> Source: $SRC"
find "$SRC" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

echo ">> Copying into $CONTAINER:/config/custom_components/"
docker cp "$SRC" "$CONTAINER:/config/custom_components/"

echo ">> Verifying import against the running HA runtime"
docker exec "$CONTAINER" python3 -c "
import importlib
for m in (
    'custom_components.warning_aggregator',
    'custom_components.warning_aggregator.check',
    'custom_components.warning_aggregator.config_flow',
    'custom_components.warning_aggregator.coordinator',
    'custom_components.warning_aggregator.binary_sensor',
    'custom_components.warning_aggregator.sensor',
):
    importlib.import_module(m)
print('import OK')
"

echo ">> Restarting $CONTAINER"
docker restart "$CONTAINER" >/dev/null

echo ">> Waiting for the API"
for _ in $(seq 1 60); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://localhost:8123/api/ || true)"
    [ "$code" = "401" ] && { echo "   HA is up (api/ -> 401)"; break; }
    sleep 2
done

echo ">> Recent log lines mentioning the integration:"
docker exec "$CONTAINER" sh -c 'grep -i warning_aggregator /config/home-assistant.log || true'

cat <<'EOF'

Done. In the HA UI:
  Settings -> Devices & Services -> Helpers -> + Create Helper -> "Warning Aggregator"
  (create at least one Label first under Settings -> Areas, labels & zones)
EOF
