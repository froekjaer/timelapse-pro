#!/usr/bin/env bash
# Build the portable Edge QA VIPLite wrapper on an Orange Pi (2026-10-05).
#
# Needs only the base image's VIPLite runtime (/usr/include/vip_lite.h,
# /lib/libNBGlinker.so, /lib/libVIPhal.so) and g++ — no AI SDK, no OpenCV.
# Build on the OLDEST supported OS (Jammy) so the binary runs on Noble too.
# The checked-in binary edge/npu_viplite/bin/edge_qa_viplite is produced by
# this script; record its sha256 in edge/npu_viplite/bin/BUILD.txt.
set -euo pipefail

SRC_DIR="${1:-/opt/timelapse/edge/npu_viplite}"
OUT="${2:-${SRC_DIR}/bin/edge_qa_viplite}"
VENDOR="${SRC_DIR}/vendor/libawnn_viplite"

mkdir -p "$(dirname "${OUT}")"
gcc -O2 -c "${VENDOR}/awnn_lib.c" -I "${VENDOR}" -o /tmp/awnn_lib.o
gcc -O2 -c "${VENDOR}/awnn_quantize.c" -I "${VENDOR}" -o /tmp/awnn_quantize.o
g++ -O2 -std=c++17 "${SRC_DIR}/edge_qa_viplite.cpp" /tmp/awnn_lib.o /tmp/awnn_quantize.o \
    -I "${VENDOR}" -lNBGlinker -lVIPhal -lm -ldl -lpthread -o "${OUT}"
rm -f /tmp/awnn_lib.o /tmp/awnn_quantize.o
echo "${OUT}"
sha256sum "${OUT}"
