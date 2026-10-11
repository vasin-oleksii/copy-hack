#!/usr/bin/env bash
# Build TypewriterPaste as a minimal macOS .app (Apple Silicon / Intel).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

APP_NAME="TypewriterPaste"
BUILD_DIR="$ROOT/.build-app"
APP_DIR="$BUILD_DIR/${APP_NAME}.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RES_DIR="$APP_DIR/Contents/Resources"

echo "→ Resolving Swift toolchain…"
if ! command -v swift >/dev/null 2>&1; then
  echo "error: Swift is required. Install Xcode or the Swift toolchain, then retry." >&2
  exit 1
fi

echo "→ swift build -c release"
swift build -c release

BIN="$(swift build -c release --show-bin-path)/${APP_NAME}"
if [[ ! -x "$BIN" ]]; then
  echo "error: built binary not found at $BIN" >&2
  exit 1
fi

echo "→ Assembling ${APP_NAME}.app"
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"
cp "$BIN" "$MACOS_DIR/${APP_NAME}"
chmod +x "$MACOS_DIR/${APP_NAME}"

cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>TypewriterPaste</string>
  <key>CFBundleDisplayName</key>
  <string>TypewriterPaste</string>
  <key>CFBundleIdentifier</key>
  <string>local.typewriterpaste.app</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>TypewriterPaste</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

OUT="$ROOT/${APP_NAME}.app"
rm -rf "$OUT"
cp -R "$APP_DIR" "$OUT"

echo "✓ Built: $OUT"
echo
echo "Next:"
echo "  1. open \"$OUT\""
echo "  2. Enable Accessibility for TypewriterPaste"
echo "  3. Copy text with Cmd+C, focus a text field, press Cmd+K"
