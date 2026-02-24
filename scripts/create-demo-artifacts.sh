#!/bin/bash
#
# Create demo artifacts for Mender Fleet Simulator
# Requires: mender-artifact tool (https://docs.mender.io/downloads)
#

set -e

# Output directory
OUTPUT_DIR="${1:-./artifacts}"
mkdir -p "$OUTPUT_DIR"

# Device types (must match config.yaml)
DEVICE_TYPES=(
    "tcu-4g-lte"           # Automotive
    "bms-controller-hvac"   # Smart Buildings
    "patient-monitor-icu"   # Medical
    "plc-gateway-modbus"    # Industrial IoT
    "pos-terminal-emv"      # Retail
)

# Versions to generate
VERSIONS=(
    "v1.0.0"
    "v1.1.0"
    "v1.2.0"
    "v2.0.0"
)

# Check if mender-artifact is installed
if ! command -v mender-artifact &> /dev/null; then
    echo "Error: mender-artifact not found"
    echo ""
    echo "Install it from: https://docs.mender.io/downloads"
    echo ""
    echo "macOS:   brew install mender-artifact"
    echo "Linux:   Download from Mender website"
    exit 1
fi

echo "Creating demo artifacts in: $OUTPUT_DIR"
echo ""

# Create a dummy payload file
PAYLOAD_FILE=$(mktemp)
echo "Demo firmware payload - $(date)" > "$PAYLOAD_FILE"
dd if=/dev/urandom bs=1024 count=100 >> "$PAYLOAD_FILE" 2>/dev/null  # Add ~100KB of random data

# Generate artifacts for each device type and version
for DEVICE_TYPE in "${DEVICE_TYPES[@]}"; do
    echo "=== Device Type: $DEVICE_TYPE ==="

    for VERSION in "${VERSIONS[@]}"; do
        ARTIFACT_NAME="${DEVICE_TYPE}-${VERSION}"
        OUTPUT_FILE="${OUTPUT_DIR}/${ARTIFACT_NAME}.mender"

        echo "  Creating: $ARTIFACT_NAME"

        mender-artifact write rootfs-image \
            --device-type "$DEVICE_TYPE" \
            --artifact-name "$ARTIFACT_NAME" \
            --file "$PAYLOAD_FILE" \
            --output-path "$OUTPUT_FILE" \
            2>/dev/null

        # Show artifact info
        SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo "    -> $OUTPUT_FILE ($SIZE)"
    done
    echo ""
done

# Cleanup
rm -f "$PAYLOAD_FILE"

# Summary
TOTAL=$(find "$OUTPUT_DIR" -name "*.mender" | wc -l | tr -d ' ')
echo "=== Summary ==="
echo "Created $TOTAL artifacts in $OUTPUT_DIR"
echo ""
echo "To upload to Mender:"
echo "  mender-cli artifacts upload $OUTPUT_DIR/*.mender"
echo ""
echo "Or use the Mender UI to upload manually."
