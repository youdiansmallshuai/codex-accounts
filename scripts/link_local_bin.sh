#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="${PROJECT_ROOT}/bin/codex-accounts"
BIN_DIR="${HOME}/.local/bin"
LINK_PATH="${BIN_DIR}/codex-accounts"

mkdir -p "${BIN_DIR}"
ln -sfn "${TARGET}" "${LINK_PATH}"
echo "linked: ${LINK_PATH} -> ${TARGET}"
