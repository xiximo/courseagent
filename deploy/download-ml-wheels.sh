#!/usr/bin/env bash
set -euo pipefail
pip install -U pip
echo "== torch (cpu only) =="
pip download -d /wheels --default-timeout=1000 --retries=15 \
  torch --index-url https://download.pytorch.org/whl/cpu
echo "== requirements-ml (reuse CPU torch, do not pull CUDA) =="
pip download -d /wheels --default-timeout=1000 --retries=15 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -r /req/requirements-ml.txt
# sentence-transformers 从 PyPI 解析 torch 时会带上 nvidia_* / triton
rm -f /wheels/nvidia_*.whl /wheels/cuda_*.whl /wheels/triton-*.whl
echo "wheel count: $(ls /wheels/*.whl 2>/dev/null | wc -l)"
ls -lh /wheels | head -40
