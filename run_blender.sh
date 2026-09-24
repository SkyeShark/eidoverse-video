#!/usr/bin/env bash
# run_blender.sh <script.py> [args...] — headless Blender in an ISOLATED user-resources folder.
#
#   bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/export_wardrobe_vrm.py
#   bash run_blender.sh <script.py> --clips a,b          # args after the script reach it after Blender's `--`
#
# Guide: docs/blender.md. `--factory-startup` starts in seconds (a full user add-on stack can take
# minutes), but run against your REAL Blender user folder it syncs the extension wheels to the empty set that
# factory settings enable, and deletes the Python packages your installed extensions depend on. So every headless
# run here gets a sandbox: BLENDER_USER_RESOURCES points at a scratch folder, and the extensions a script needs are
# copied into it (again whenever your installed copy changes). Scripts enable them with
# bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.<name>').
#
# Environment:
#   BLENDER          the Blender executable (default: `blender` on PATH, then common install folders, newest first)
#   BLENDER_SANDBOX  the isolated user folder (default: $TMP/blender_user_isolated)
#   BLENDER_EXTS     extensions to copy into the sandbox, space-separated (default: vrm — the VRM Add-on for Blender)
set -e
[ -n "$1" ] || { echo "usage: bash run_blender.sh <script.py> [args...]" >&2; exit 2; }

if [ -z "$BLENDER" ]; then
    if command -v blender >/dev/null 2>&1; then
        BLENDER="$(command -v blender)"
    else
        for c in $(ls -d "$HOME"/Blender/*/blender.exe "/c/Program Files/Blender Foundation/"*/blender.exe \
                   /Applications/Blender.app/Contents/MacOS/Blender /usr/bin/blender /snap/bin/blender 2>/dev/null | sort -rV); do
            BLENDER="$c"; break
        done
    fi
fi
[ -n "$BLENDER" ] && [ -e "$BLENDER" ] || { echo "run_blender.sh: Blender not found; set BLENDER=/path/to/blender" >&2; exit 2; }

# your real Blender user folders (every version), newest first: where installed extensions are copied from
USER_DIRS=$(ls -d "${APPDATA:-/nonexistent}/Blender Foundation/Blender/"*/ "$HOME/Library/Application Support/Blender/"*/ \
            "$HOME/.config/blender/"*/ 2>/dev/null | sort -rV || true)
SANDBOX="${BLENDER_SANDBOX:-${TMP:-/tmp}/blender_user_isolated}"
mkdir -p "$SANDBOX/extensions/blender_org"
for ext in ${BLENDER_EXTS:-vrm}; do
    src=""
    while IFS= read -r d; do
        for repo in "$d"extensions/*/; do
            if [ -f "$repo$ext/blender_manifest.toml" ]; then src="$repo$ext"; break 2; fi
        done
    done <<< "$USER_DIRS"
    dst="$SANDBOX/extensions/blender_org/$ext"
    if [ -z "$src" ]; then
        [ -d "$dst" ] || echo "run_blender.sh: extension '$ext' is not installed in your Blender; install it once from extensions.blender.org (Edit > Preferences > Get Extensions)" >&2
    elif ! cmp -s "$src/blender_manifest.toml" "$dst/blender_manifest.toml"; then
        rm -rf "$dst"
        cp -r "$src" "$dst"
        echo "run_blender.sh: copied extension '$ext' into the sandbox" >&2
    fi
done

export BLENDER_USER_RESOURCES="$SANDBOX"
export PYTHONUNBUFFERED=1
S="$1"; shift
exec "$BLENDER" --background --factory-startup --python "$S" -- "$@"
