"""
数据库初始化脚本
用于确保数据库表结构完整
"""

import os
from pathlib import Path
from .db import init_database, get_db_connection


def ensure_tables_exist():
    """
    确保所有需要的表都存在
    """
    db_path = os.path.join(Path(__file__).resolve().parent.parent, 'recommend.db')
    
    # 初始化数据库（会创建所有表，如果不存在的话）
    init_database(db_path)
    
    # 验证所有表是否存在
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 检查posts表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='posts';
    """)
    posts_table_exists = cursor.fetchone() is not None
    
    # 检查users表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='users';
    """)
    users_table_exists = cursor.fetchone() is not None
    
    # 检查comments表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='comments';
    """)
    comments_table_exists = cursor.fetchone() is not None
    
    # 检查user_actions表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='user_actions';
    """)
    user_actions_table_exists = cursor.fetchone() is not None
    
    conn.close()
    
    print(f"数据库表状态检查:")
    print(f"- posts表: {'✓' if posts_table_exists else '✗'}")
    print(f"- users表: {'✓' if users_table_exists else '✗'}")
    print(f"- comments表: {'✓' if comments_table_exists else '✗'}")
    print(f"- user_actions表: {'✓' if user_actions_table_exists else '✗'}")
    
    all_tables_exist = all([
        posts_table_exists,
        users_table_exists,
        comments_table_exists,
        user_actions_table_exists
    ])
    
    if all_tables_exist:
        print("所有数据库表均已存在，无需初始化。")
    else:
        print("正在创建缺失的数据库表...")
        init_database(db_path)
        print("数据库表创建完成！")
    
    return all_tables_exist


if __name__ == "__main__":
    ensure_tables_exist()