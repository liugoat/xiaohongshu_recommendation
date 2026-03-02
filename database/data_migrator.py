"""
JSON数据迁移到SQLite数据库的脚本
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from .db import get_db_connection, check_and_init_database


def migrate_json_to_sqlite(json_path=None, db_path=None):
    """
    将JSON数据迁移到SQLite数据库
    :param json_path: JSON文件路径，默认为项目data目录下的mock_posts.json
    :param db_path: 数据库文件路径，默认为项目根目录下的recommend.db
    """
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mock_posts.json')
    
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    # 检查并初始化数据库
    check_and_init_database(db_path)
    
    # 读取JSON数据
    if not os.path.exists(json_path):
        print(f"JSON文件 {json_path} 不存在，无法迁移数据")
        return False
    
    with open(json_path, 'r', encoding='utf-8') as f:
        posts_data = json.load(f)
    
    print(f"开始迁移 {len(posts_data)} 条帖子数据到数据库...")
    
    # 连接到数据库
    conn = get_db_connection(db_path)
    
    # 清空现有数据（可选，根据需要决定是否清空）
    conn.execute("DELETE FROM posts")
    
    # 插入数据
    for post in posts_data:
        # 将标签和图片数组转换为JSON字符串
        tags_json = json.dumps(post.get('tags', []), ensure_ascii=False)
        images_json = json.dumps(post.get('images', []), ensure_ascii=False)
        
        # 插入帖子数据
        conn.execute('''
            INSERT INTO posts (post_id, title, content, tags, images, likes, comments, collects, publish_time, hot_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            post.get('post_id'),
            post.get('title', ''),
            post.get('content', ''),
            tags_json,
            images_json,
            post.get('likes', 0),
            post.get('comments', 0),
            post.get('collects', 0),
            post.get('publish_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            post.get('hot_score', 0)
        ))
    
    conn.commit()
    conn.close()
    
    print(f"成功迁移 {len(posts_data)} 条帖子数据到数据库！")
    return True


def migrate_users_to_sqlite(json_path=None, db_path=None):
    """
    将用户数据迁移到SQLite数据库
    :param json_path: JSON文件路径，默认为项目data目录下的users.json
    :param db_path: 数据库文件路径，默认为项目根目录下的recommend.db
    """
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'users.json')
    
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    # 检查并初始化数据库
    check_and_init_database(db_path)
    
    # 读取JSON数据
    if not os.path.exists(json_path):
        print(f"用户JSON文件 {json_path} 不存在，使用默认用户数据")
        # 创建默认用户数据
        users_data = [
            {
                "user_id": 1,
                "username": "xiaohong",
                "password": "e10adc3949ba59abbe56e057f20f883e",  # 123456的MD5
                "nickname": "勇敢的人先享受世界",
                "avatar": "https://via.placeholder.com/40x40/ff2a68/ffffff?text=头像"
            },
            {
                "user_id": 2,
                "username": "xiaobai",
                "password": "e10adc3949ba59abbe56e057f20f883e",  # 123456的MD5
                "nickname": "小百科",
                "avatar": "https://via.placeholder.com/40x40/4CAF50/ffffff?text=小"
            }
        ]
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
    
    print(f"开始迁移 {len(users_data)} 条用户数据到数据库...")
    
    # 连接到数据库
    conn = get_db_connection(db_path)
    
    # 清空现有用户数据（可选）
    conn.execute("DELETE FROM users")
    
    # 插入用户数据
    for user in users_data:
        conn.execute('''
            INSERT INTO users (user_id, username, password, nickname, avatar)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user.get('user_id'),
            user.get('username'),
            user.get('password'),
            user.get('nickname', ''),
            user.get('avatar')
        ))
    
    conn.commit()
    conn.close()
    
    print(f"成功迁移 {len(users_data)} 条用户数据到数据库！")
    return True


def migrate_comments_to_sqlite(json_path=None, db_path=None):
    """
    将评论数据迁移到SQLite数据库
    :param json_path: JSON文件路径，默认为项目data目录下的comments.json
    :param db_path: 数据库文件路径，默认为项目根目录下的recommend.db
    """
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'comments.json')
    
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    # 检查并初始化数据库
    check_and_init_database(db_path)
    
    # 检查comments表是否存在
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='comments';
    """)
    table_exists = cursor.fetchone() is not None
    conn.close()
    
    if not table_exists:
        print("comments表不存在，跳过评论数据迁移")
        return True
    
    # 读取JSON数据
    if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
        print(f"评论JSON文件 {json_path} 不存在或为空，跳过评论数据迁移")
        return True
    
    with open(json_path, 'r', encoding='utf-8') as f:
        comments_data = json.load(f)
    
    print(f"开始迁移 {len(comments_data)} 条评论数据到数据库...")
    
    # 连接到数据库
    conn = get_db_connection(db_path)
    
    # 清空现有评论数据（可选）
    conn.execute("DELETE FROM comments")
    
    # 插入评论数据
    for comment in comments_data:
        conn.execute('''
            INSERT INTO comments (comment_id, post_id, user_id, content, publish_time, likes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            comment.get('comment_id'),
            comment.get('post_id'),
            comment.get('user_id'),
            comment.get('content', ''),
            comment.get('publish_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            comment.get('likes', 0)
        ))
    
    conn.commit()
    conn.close()
    
    print(f"成功迁移 {len(comments_data)} 条评论数据到数据库！")
    return True


def migrate_all_data():
    """
    迁移所有数据（帖子、用户和评论）
    """
    print("开始迁移所有数据到SQLite数据库...")
    
    # 迁移帖子数据
    migrate_json_to_sqlite()
    
    # 迁移用户数据
    migrate_users_to_sqlite()
    
    # 迁移评论数据
    migrate_comments_to_sqlite()
    
    print("数据迁移完成！")


if __name__ == "__main__":
    migrate_all_data()