"""
数据库连接与初始化模块
提供SQLite数据库的基础操作和初始化功能
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path


def get_db_connection(db_path=None):
    """
    获取数据库连接
    :param db_path: 数据库文件路径，默认为项目根目录下的 recommend.db
    :return: 数据库连接对象
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
    return conn


def init_database(db_path=None):
    """
    初始化数据库，创建所需的表
    :param db_path: 数据库文件路径，默认为项目根目录下的 recommend.db
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    conn = get_db_connection(db_path)
    
    # 创建posts表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT NOT NULL,           -- JSON格式存储标签数组
            images TEXT NOT NULL,         -- JSON格式存储图片数组
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            collects INTEGER DEFAULT 0,
            publish_time TEXT NOT NULL,   -- 格式: YYYY-MM-DD HH:MM:SS
            hot_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建users表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,       -- MD5加密后的密码
            nickname TEXT NOT NULL,
            avatar TEXT,
            profile_tags TEXT,            -- JSON格式存储用户标签
            user_type TEXT,               -- 用户类型
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 为已存在的users表添加缺失的列（如果需要）
    try:
        conn.execute('ALTER TABLE users ADD COLUMN user_type TEXT')
    except sqlite3.OperationalError:
        # 如果列已存在，会抛出异常，这是正常的
        pass
    
    # 创建comments表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            publish_time TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            FOREIGN KEY (post_id) REFERENCES posts (post_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # 创建user_actions表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,    -- 'view', 'like', 'collect', 'comment'
            action_time TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (post_id) REFERENCES posts (post_id)
        )
    ''')

    # 新增 post_tags 表，用于将 tags 拆分为关系型表以支持高效查询
    conn.execute('''
        CREATE TABLE IF NOT EXISTS post_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts (post_id)
        )
    ''')
    
    # 创建索引以提高查询性能
    conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_hot_score ON posts(hot_score DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_publish_time ON posts(publish_time DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_tags ON posts(tags)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_post_tags_tag ON post_tags(tag)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_user_post ON user_actions(user_id, post_id, action_type)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions(action_type)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_user_actions_action_time ON user_actions(action_time)')
    
    conn.commit()
    conn.close()


def check_and_init_database(db_path=None):
    """
    检查数据库是否存在，不存在则创建并初始化
    :param db_path: 数据库文件路径
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recommend.db')
    
    if not os.path.exists(db_path):
        print(f"数据库 {db_path} 不存在，正在创建并初始化...")
        init_database(db_path)
        print("数据库初始化完成！")


# 数据库ER图说明
"""
数据库实体关系图 (ER Diagram):

posts 表:
- post_id: 帖子唯一标识符
- title: 标题
- content: 内容
- tags: 标签(JSON格式)
- images: 图片列表(JSON格式)
- likes: 点赞数
- comments: 评论数
- collects: 收藏数
- publish_time: 发布时间
- hot_score: 热度分数
- created_at: 创建时间

users 表:
- user_id: 用户唯一标识符
- username: 用户名
- password: 密码(MD5加密)
- nickname: 昵称
- avatar: 头像URL
- profile_tags: 用户画像标签(JSON格式)
- created_at: 创建时间

comments 表:
- comment_id: 评论唯一标识符
- post_id: 帖子ID(外键关联posts表)
- user_id: 用户ID(外键关联users表)
- content: 评论内容
- publish_time: 评论时间
- likes: 评论点赞数

user_actions 表:
- id: 操作记录唯一标识符
- user_id: 用户ID(外键关联users表)
- post_id: 帖子ID(外键关联posts表)
- action_type: 操作类型('like', 'collect', 'comment')
- action_time: 操作时间

关系:
- users 一对多 comments (一个用户可以发表多条评论)
- posts 一对多 comments (一个帖子可以有多条评论)
- users 一对多 user_actions (一个用户可以有多次操作)
- posts 一对多 user_actions (一个帖子可以被多次操作)
"""