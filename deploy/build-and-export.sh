#!/usr/bin/env bash
# 单独构建并导出 backend / web 镜像
# 用法: ./deploy/build-and-export.sh [backend|web|all]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TARGET="${1:-all}"
OUT_DIR="$ROOT/deploy/dist"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

build_save() {
  local name="$1" context="$2" image="$3"
  echo "==> docker build $name"
  docker build -t "$image" "$context"
  local tar="$OUT_DIR/${name}-${STAMP}.tar"
  echo "==> docker save $image -> $tar"
  docker save -o "$tar" "$image"
  echo "完成: $tar ($(du -h "$tar" | cut -f1))"
}

case "$TARGET" in
  backend) build_save courseagent-backend ./backend courseagent-backend:latest ;;
  web) build_save courseagent-web ./webadmin courseagent-web:latest ;;
  all)
    build_save courseagent-backend ./backend courseagent-backend:latest
    build_save courseagent-web ./webadmin courseagent-web:latest
    ;;
  *) echo "用法: $0 [backend|web|all]"; exit 1 ;;
esac

echo
echo "服务器: docker load -i <tar> 后按 deploy/README.md 启动"
