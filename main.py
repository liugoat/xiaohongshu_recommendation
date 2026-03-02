"""
项目主入口
生成模拟数据并启动后端服务
"""
import os
import sys
import json
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve()
sys.path.insert(0, str(project_root.parent))

from mock_data.exporter import export_mock_data_to_db
from backend.app import create_app
from database.data_migrator import migrate_all_data
from database.db import check_and_init_database


def main():
    """
    项目主函数
    1. 检查并初始化数据库
    2. 迁移数据到数据库
    3. 启动后端服务
    """
    print("=== 小红书热门笔记推荐系统（数据库版）===")
    
    # 确保数据库已初始化
    print("正在检查数据库状态...")
    check_and_init_database()
    
    # 生成模拟数据
    print("正在生成模拟数据...")
    export_mock_data_to_db(post_count=2000, user_count=35)
    
    # 创建并启动Flask应用
    print("正在启动后端服务...")
    app = create_app()
    
    # 获取主机和端口配置
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    print(f"服务将在 http://{host}:{port} 上启动")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()