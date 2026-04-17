# -*- coding: utf-8 -*-
"""数据库模块"""
import sqlite3
import os
from .config import DB_PATH, PHOTO_DIR


def init_db():
    """初始化数据库表结构"""
    os.makedirs(PHOTO_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 建 members 表
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            birth_date TEXT,
            death_date TEXT,
            father_id INTEGER,
            mother_id INTEGER,
            bio TEXT,
            photo_path TEXT,
            extra_photos TEXT,
            generation INTEGER DEFAULT 0,
            x_pos REAL DEFAULT 0,
            y_pos REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 迁移：补充 spouse1_id / spouse2_id 列
    c.execute("PRAGMA table_info(members)")
    columns = [row[1] for row in c.fetchall()]
    if "spouse_id" not in columns:
        c.execute("ALTER TABLE members ADD COLUMN spouse_id INTEGER")
    if "spouse1_id" not in columns:
        c.execute("ALTER TABLE members ADD COLUMN spouse1_id INTEGER")
    if "spouse2_id" not in columns:
        c.execute("ALTER TABLE members ADD COLUMN spouse2_id INTEGER")
    # 旧 spouse_id → spouse1_id
    if "spouse_id" in columns and "spouse1_id" in columns:
        c.execute("UPDATE members SET spouse1_id=spouse_id WHERE spouse_id IS NOT NULL AND spouse1_id IS NULL")
        c.execute("DROP INDEX IF EXISTS idx_spouse_id")

    # 建 photo_wall 表
    c.execute("""
        CREATE TABLE IF NOT EXISTS photo_wall (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            caption TEXT,
            member_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 建 stories 表（故事摘要）
    c.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            author TEXT,
            created_at TEXT,
            member_id INTEGER,
            image_path TEXT
        )
    """)
    # 迁移：为已存在的 stories 表添加 image_path 列（若无此列）
    try:
        c.execute("ALTER TABLE stories ADD COLUMN image_path TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def get_conn():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)
