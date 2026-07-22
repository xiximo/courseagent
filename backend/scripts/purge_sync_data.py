"""批量清理 SPRS 同步产生的标准元数据、任务记录与 MinIO 附件。

用法（在 backend 目录下）:
  .\\.venv\\Scripts\\python scripts/purge_sync_data.py --yes
  .\\.venv\\Scripts\\python scripts/purge_sync_data.py --yes --minio-only
  .\\.venv\\Scripts\\python scripts/purge_sync_data.py --yes --db-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal
from app.services.purge_sync import (
    MINIO_PREFIX,
    purge_sync_database,
    purge_sync_minio,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 SPRS 同步数据与附件")
    parser.add_argument("--yes", action="store_true", help="确认执行")
    parser.add_argument("--db-only", action="store_true", help="仅清理数据库")
    parser.add_argument("--minio-only", action="store_true", help="仅清理 MinIO 附件")
    args = parser.parse_args()

    do_db = not args.minio_only
    do_minio = not args.db_only

    print("将清理以下内容（保留 sprs_config、user_account）：")
    if do_db:
        print("  - PostgreSQL: standard, attachment, sync_job, sync_job_log 等")
    if do_minio:
        print(f"  - MinIO: bucket 下前缀 {MINIO_PREFIX!r}")

    if not args.yes:
        print("\n预览模式，未执行删除。请加 --yes 确认。")
        return

    if do_db:
        with SessionLocal() as db:
            counts = purge_sync_database(db)
        print("数据库已清理:", counts)

    if do_minio:
        removed = purge_sync_minio()
        print(f"MinIO 已删除对象数: {removed}")

    print("完成。")


if __name__ == "__main__":
    main()
