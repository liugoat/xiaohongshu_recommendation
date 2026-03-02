"""
数据导出与初始化脚本
用于生成和导出模拟数据到数据库
"""

import json
import sqlite3
from datetime import datetime
import random
import os
from pathlib import Path

# 添加项目根目录到sys.path，以解决导入问题
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from mock_data.post_generator import generate_post
from mock_data.generate_user_actions import UserActionsGenerator
from database.db import init_database


def check_data_exists(db_path, threshold=2000):
    """
    检查数据库中是否已有足够的帖子数据
    :param db_path: 数据库路径
    :param threshold: 数据量阈值
    :return: 如果数据量足够返回True，否则返回False
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM posts")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"数据库中已有 {count} 条帖子数据，阈值为 {threshold}")
    return count >= threshold


def check_user_data_exists(db_path, threshold=35):
    """
    检查数据库中是否已有足够的用户数据
    :param db_path: 数据库路径
    :param threshold: 数据量阈值
    :return: 如果数据量足够返回True，否则返回False
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE username LIKE 'sim_user_%'")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"数据库中已有 {count} 个模拟用户数据，阈值为 {threshold}")
    return count >= threshold


def export_data():
    """
    导出数据的兼容函数接口
    """
    export_mock_data_to_db()


def export_mock_data_to_db(post_count=2000, user_count=35):
    """
    将模拟数据导出到数据库
    """
    # 获取数据库路径
    db_path = os.path.join(project_root, 'recommend.db')
    
    # 初始化数据库
    init_database(db_path)
    
    # 检查是否已有足够的帖子数据
    if check_data_exists(db_path, post_count):
        print("数据库中已有足够的帖子数据，跳过重新生成")
    else:
        print("开始生成帖子数据...")
        # 生成帖子数据
        posts_data = []
        for i in range(1, post_count + 1):
            post = generate_post(i)
            posts_data.append(post)
        
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 清空现有数据
        cursor.execute("DELETE FROM posts")
        print("已清空现有帖子数据")
        
        # 插入帖子数据
        for post in posts_data:
            cursor.execute("""
                INSERT INTO posts 
                (post_id, title, content, tags, images, likes, comments, collects, publish_time, hot_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post['post_id'], 
                post['title'], 
                post['content'], 
                json.dumps(post['tags']), 
                json.dumps(post['images']), 
                post['likes'], 
                post['comments'], 
                post['collects'], 
                post['publish_time'], 
                0.0  # 初始热度分数
            ))
        
        conn.commit()
        conn.close()
        
        print(f"成功生成 {post_count} 条帖子数据")
    
    # 检查是否已有足够的用户数据
    if check_user_data_exists(db_path, user_count):
        print("数据库中已有足够的用户数据，跳过重新生成用户")
    else:
        print("开始生成用户行为数据...")
        generator = UserActionsGenerator(db_path=db_path)
        generator.generate(user_count=user_count, actions_per_user=(30, 100))