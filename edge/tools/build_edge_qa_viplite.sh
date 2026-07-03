#!/usr/bin/env bash
set -euo pipefail

AI_SDK_ROOT="${AI_SDK_ROOT:-/opt/timelapse/ai-sdk}"
SRC_DIR="${1:-/opt/timelapse/edge/npu_viplite}"
BUILD_DIR="${2:-${SRC_DIR}/build}"
INSTALL_BIN="${INSTALL_BIN:-/opt/timelapse/bin/edge_qa_viplite}"

cmake -S "${SRC_DIR}" -B "${BUILD_DIR}" -DAI_SDK_ROOT="${AI_SDK_ROOT}"
cmake --build "${BUILD_DIR}" -j"$(nproc)"

mkdir -p "$(dirname "${INSTALL_BIN}")"
install -m 0755 "${BUILD_DIR}/edge_qa_viplite" "${INSTALL_BIN}"
echo "${INSTALL_BIN}"
