"""
后端Flask应用
提供推荐系统API服务
"""
import os
import sys
# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_cors import CORS
import uuid  # 用于生成会话ID

app = Flask(__name__)


def create_app():
    """创建Flask应用实例"""
    # 在创建应用时确保数据库表存在
    from database.init_db import ensure_tables_exist
    ensure_tables_exist()
    
    app = Flask(__name__, 
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend'),
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend'))
    
    # 配置
    app.config['JSON_AS_ASCII'] = False
    app.config['JSON_SORT_KEYS'] = False
    
    # 导入路由
    from .routes import init_routes
    from .advanced_routes import init_advanced_routes
    init_routes(app)
    init_advanced_routes(app)

    # Enable CORS for API endpoints. Adjust `origins` as needed for production.
    # Allows browser clients to send cookies when `credentials: 'include'` is used
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    
    return app
