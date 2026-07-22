"""初始化 course 数据库：建表 + 种子数据。

用法（在 backend 目录）:
  python -m scripts.init_course_db
"""

from app.course_agent.bootstrap import init_database


def main() -> None:
    init_database()
    print("course 数据库初始化完成")


if __name__ == "__main__":
    main()
