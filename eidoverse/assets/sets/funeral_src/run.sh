#!/usr/bin/env bash
# run.sh <script.py> [args] — run a funeral-set Blender builder headless THROUGH THE ISOLATED RUNNER.
# Never call blender.exe directly against a real user config: a headless --factory-startup run there
# strips the installed extension wheels (seen 2026-09-23). The repository's run_blender.sh points
# BLENDER_USER_RESOURCES at a scratch sandbox. The builders only need core Blender (no add-ons).
# Run from the working layout the builders were written for: this folder copied to work/daisy/sets/blender/
# (see README.md), so the repository root is four levels up.
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
cd "$HERE"
bash "$REPO/run_blender.sh" "$HERE/$1" "${@:2}" 2>&1 \
  | grep -v -E "register_class|__slots__|bl_info|Warning: '|WARNING:|^\s*$"
