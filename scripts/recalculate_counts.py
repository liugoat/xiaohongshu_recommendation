"""
离线校验脚本：根据 comments / user_actions 表重算 posts 表中的 likes/comments/collects
用法：在维护窗口或测试环境运行
    python scripts/recalculate_counts.py
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = os.path.join(Path(__file__).resolve().parent.parent, 'recommend.db')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print('开始重算 posts 表计数...')

# 重算 comments
cursor.execute('SELECT post_id, COUNT(*) as cnt FROM comments GROUP BY post_id')
for row in cursor.fetchall():
    cursor2 = conn.cursor()
    cursor2.execute('UPDATE posts SET comments = ? WHERE post_id = ?', (row['cnt'], row['post_id']))
    cursor2.close()

# 重算 likes (从 user_actions 中统计 action_type='like')
cursor.execute("SELECT post_id, COUNT(*) as cnt FROM user_actions WHERE action_type = 'like' GROUP BY post_id")
for row in cursor.fetchall():
    cursor2 = conn.cursor()
    cursor2.execute('UPDATE posts SET likes = ? WHERE post_id = ?', (row['cnt'], row['post_id']))
    cursor2.close()

# 重算 collects
cursor.execute("SELECT post_id, COUNT(*) as cnt FROM user_actions WHERE action_type = 'collect' GROUP BY post_id")
for row in cursor.fetchall():
    cursor2 = conn.cursor()
    cursor2.execute('UPDATE posts SET collects = ? WHERE post_id = ?', (row['cnt'], row['post_id']))
    cursor2.close()

conn.commit()
print('重算完成：posts.likes/comments/collects 已更新')
conn.close()
