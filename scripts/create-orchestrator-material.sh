#!/bin/bash
#
# Create Orchestrator demo material (component artifacts + manifests) for the
# system profiles of the simulator (see docs/orchestrator-simulation.md).
#
# Requires: mender-artifact and scripts/mender-orchestrator-manifest-gen
# (vendored from mendersoftware/mender-orchestrator-support).
#
# Usage:
#   $0 <system-core|lv-site> [output_dir]
#
# To upload, set MENDER_URL (default https://hosted.mender.io) and TOKEN (a
# PAT of the target tenant). Component artifacts go to the classic artifacts
# API; manifests MUST go to the v1alpha1 manifests API (the classic endpoint
# rejects the mender-orchestrator-manifest type).

set -e
cd "$(dirname "$0")/.."

PROFILE="${1:-}"
OUTPUT_DIR="${2:-./artifacts/orchestrator}"
GEN=scripts/mender-orchestrator-manifest-gen
MENDER_URL="${MENDER_URL:-https://hosted.mender.io}"

usage() {
    echo "Usage: $0 <system-core|lv-site> [output_dir]"
    exit 1
}

# Profile definitions: system_type, manifest name prefix and components as
# "component_type:version_prefix:order" triplets.
case "$PROFILE" in
    system-core)
        SYSTEM_TYPE="system-core"
        COMPONENTS="gateway:gateway:10 rtos:rtos:20"
        ;;
    lv-site)
        SYSTEM_TYPE="lv-monitoring-site"
        COMPONENTS="edge-gateway:lvgw:10 line-sensor:lsensor-fw:20 weather-station:wx-fw:30"
        ;;
    *) usage ;;
esac

command -v mender-artifact >/dev/null || {
    echo "Error: mender-artifact not found (brew install mender-artifact)"
    exit 1
}

mkdir -p "$OUTPUT_DIR"
echo "Creating Orchestrator material for $PROFILE in $OUTPUT_DIR"

## ---- Component artifacts (module-image, empty payload) ---------------------
PAYLOAD=$(mktemp)
for v in v1 v2; do
    for spec in $COMPONENTS; do
        CTYPE="${spec%%:*}"
        rest="${spec#*:}"
        PREFIX="${rest%%:*}"
        NAME="$PREFIX-$v"
        mender-artifact write module-image \
            --type "${CTYPE}-interface" \
            --compatible-types "$CTYPE" \
            --file "$PAYLOAD" \
            --output-path "$OUTPUT_DIR/$NAME.mender" \
            --artifact-name "$NAME" 2>/dev/null
        echo "  component artifact: $NAME.mender ($CTYPE)"
    done
done
rm -f "$PAYLOAD"

## ---- Manifests --------------------------------------------------------------
# NOTE: no --artifact-name — the server requires the Artifact name to EQUAL
# the manifest's `name`; manifest-gen uses the manifest name when omitted.
for v in v1 v2; do
    MANIFEST_NAME="$PROFILE-$v"
    YAML="$OUTPUT_DIR/$MANIFEST_NAME.yaml"
    {
        echo 'api_version: "mender/v1"'
        echo 'kind: "manifest"'
        echo "name: \"$MANIFEST_NAME\""
        echo "system_types_compatible: [\"$SYSTEM_TYPE\"]"
        echo "component_types:"
        for spec in $COMPONENTS; do
            CTYPE="${spec%%:*}"
            rest="${spec#*:}"
            PREFIX="${rest%%:*}"
            ORDER="${rest#*:}"
            echo "  $CTYPE:"
            echo "    artifact_name: $PREFIX-$v"
            echo "    update_strategy: { order: $ORDER }"
        done
    } > "$YAML"
    "$GEN" --output-path "$OUTPUT_DIR/$MANIFEST_NAME.mender" \
        --system-type "$SYSTEM_TYPE" "$YAML" > /dev/null
    echo "  manifest: $MANIFEST_NAME.mender"
done

## ---- Optional upload ---------------------------------------------------------
if [ -z "$TOKEN" ]; then
    echo ""
    echo "TOKEN not set: skipping upload. To upload, run with:"
    echo "  TOKEN=<PAT> $0 $PROFILE $OUTPUT_DIR"
    exit 0
fi

echo ""
echo "Uploading to $MENDER_URL ..."
for f in "$OUTPUT_DIR"/*.mender; do
    name=$(basename "$f" .mender)
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f")
    case "$name" in
        "$PROFILE"-v*)  # manifests -> v1alpha1 API
            endpoint="$MENDER_URL/api/management/v1alpha1/deployments/manifests"
            ;;
        *)              # component artifacts -> classic API
            endpoint="$MENDER_URL/api/management/v1/deployments/artifacts"
            ;;
    esac
    code=$(curl -s -o /tmp/orch-upload.txt -w "%{http_code}" -X POST "$endpoint" \
        -H "Authorization: Bearer $TOKEN" \
        -F "size=$size" \
        -F "artifact=@$f;type=application/octet-stream")
    echo "  $name -> HTTP $code"
    [ "$code" = "201" ] || [ "$code" = "409" ] || cat /tmp/orch-upload.txt
done
