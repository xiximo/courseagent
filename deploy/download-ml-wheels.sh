#!/usr/bin/env bash
set -euo pipefail
pip install -U pip
echo "== torch (cpu) =="
pip download -d /wheels --default-timeout=1000 --retries=15 \
  torch --index-url https://download.pytorch.org/whl/cpu \
  || pip download -d /wheels --default-timeout=1000 --retries=15 torch \
       -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "== requirements-ml =="
pip download -d /wheels --default-timeout=1000 --retries=15 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  -r /req/requirements-ml.txt
echo "wheel count: $(ls /wheels/*.whl 2>/dev/null | wc -l)"
ls -lh /wheels | head -40
