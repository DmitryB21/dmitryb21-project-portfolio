#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/../build_frontend"
ARCHIVE_NAME="standalone_frontend_$(date +%Y%m%d_%H%M%S).tar.gz"

echo "==> Preparing build directory: $BUILD_DIR"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "==> Copying frontend files"
cp -R "$PROJECT_ROOT"/* "$BUILD_DIR"/

echo "==> Creating archive: $ARCHIVE_NAME"
cd "$BUILD_DIR/.."
tar -czf "$ARCHIVE_NAME" "$(basename "$BUILD_DIR")"

echo "==> Done"
echo "Archive path: $(pwd)/$ARCHIVE_NAME"


