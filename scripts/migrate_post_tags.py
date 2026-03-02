"""
迁移脚本：将 posts.tags(JSON) 中的标签拆分到 post_tags 表
使用：在测试环境或备份数据库后运行：
    python scripts/migrate_post_tags.py
"""
import sqlite3
import json
import os
from pathlib import Path

DB_PATH = os.path.join(Path(__file__).resolve().parent.parent, 'recommend.db')

BATCH_SIZE = 500


def safe_json_loads(value):
    if value is None:
        return []
    try:
        if isinstance(value, (list, dict)):
            return value
        s = str(value).strip()
        if s == '' or s.lower() == 'null':
            return []
        return json.loads(s)
    except Exception:
        return []


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 确保 post_tags 表存在（db.init_database 已新增建表语句，但在旧库可能不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts (post_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_post_tags_tag ON post_tags(tag)')
    conn.commit()

    # 遍历 posts，批量插入 tag
    cursor.execute('SELECT post_id, tags FROM posts')
    rows = cursor.fetchall()
    total = len(rows)
    print(f"Found {total} posts to migrate tags")

    inserted = 0
    for row in rows:
        post_id = row['post_id']
        tags = safe_json_loads(row['tags'])
        if not tags:
            continue
        # 删除旧的 post_tags entries for this post 防止重复
        cursor.execute('DELETE FROM post_tags WHERE post_id = ?', (post_id,))
        for tag in tags:
            t = tag.strip()
            if not t:
                continue
            cursor.execute('INSERT INTO post_tags (post_id, tag) VALUES (?, ?)', (post_id, t))
            inserted += 1
        if inserted % BATCH_SIZE == 0:
            conn.commit()
            print(f"Inserted {inserted} post_tags so far...")
    conn.commit()
    print(f"Migration complete. Inserted {inserted} post_tags records.")
    conn.close()


if __name__ == '__main__':
    migrate()
