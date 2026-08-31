#!/bin/sh
# Sparse-checkout the HackTricks web tree. License is CC-BY-NC-SA — see
# scanner/knowledge/hacktricks-web/NOTICE.md before using in an image.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEST="$ROOT/scanner/knowledge/hacktricks-web"
TMP="${TMPDIR:-/tmp}/hacktricks-web-$$"
git clone --depth 1 --filter=blob:none --sparse https://github.com/HackTricks-wiki/hacktricks.git "$TMP"
git -C "$TMP" sparse-checkout set src/pentesting-web
rm -rf "$DEST/pentesting-web"
mkdir -p "$DEST"
cp -R "$TMP/src/pentesting-web" "$DEST/pentesting-web"
rm -rf "$TMP"
echo "Vendored HackTricks web tree into $DEST/pentesting-web"
