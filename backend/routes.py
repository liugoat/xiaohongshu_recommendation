"""
会话管理工具模块
"""
from datetime import datetime
import uuid  # 添加uuid导入

# 使用 SessionStore 抽象管理会话，具体实现位于 backend/session_store.py
from .session_store import session_store


def get_user_by_session(session_id):
    """根据会话ID获取用户信息（通过 SessionStore）"""
    if not session_id:
        return None
    return session_store.get(session_id)

"""
API路由定义
重构后使用数据库数据
"""
from flask import request, jsonify, send_from_directory, make_response
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import json  # 添加json导入

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Flask相关导入
from flask import Flask, request, jsonify

# 数据库DAO导入
from database.dao import PostDAO
from database.dao import UserDAO
from database.dao import UserActionDAO
from database.dao import CommentDAO

# 推荐系统导入 - 已不再使用，改用服务层
# from recommendation.recommender import recommend_posts
# from recommendation.personalized_recommend import get_personalized_posts

# 服务层导入
from service.recommend_service import RecommendService

# 注意：这里不再从utils.session_manager导入，因为函数已在上面定义


def init_routes(app):
    """
    初始化路由
    
    Args:
        app (Flask): Flask应用实例
    """

    @app.route('/')
    def index():
        """
        首页，返回前端页面
        """
        return send_from_directory(os.path.join(app.root_path, '..', 'frontend'), 'index.html')

    @app.route('/frontend/<path:filename>')
    def frontend_files(filename):
        """
        静态文件服务
        """
        return send_from_directory(os.path.join(app.root_path, '..', 'frontend'), filename)

    @app.route('/api/register', methods=['POST'])
    def register():
        """
        用户注册
        Request Body:
            username (str): 用户名
            password (str): 密码
            nickname (str): 昵称
        
        Returns:
            JSON: 注册结果和用户信息
        """
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        nickname = data.get('nickname') or f"用户{len(UserDAO.get_all_users()) + 1 if hasattr(UserDAO, 'get_all_users') else 1}"

        # 参数校验
        if not username or not password or not nickname:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400

        if not (3 <= len(username) <= 20):
            return jsonify({'success': False, 'message': '用户名长度必须在3-20个字符之间'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': '密码长度至少为6位'}), 400

        # 先检查是否存在（快速失败），以减少不必要的插入尝试
        existing_user = UserDAO.get_user_by_username(username)
        if existing_user:
            return jsonify({'success': False, 'message': '用户名已存在'}), 409

        # 创建用户，捕获唯一约束冲突（并发场景）
        password_hash = generate_password_hash(password)
        avatar = f"https://via.placeholder.com/40x40/ff2a68/ffffff?text={nickname[0]}" if nickname else None

        try:
            created = UserDAO.create_user(username, password_hash, nickname, avatar)
        except Exception as e:
            # 如果 DAO 抛出异常，视为服务器错误
            return jsonify({'success': False, 'message': f'注册失败: {str(e)}'}), 500

        if not created:
            # 创建失败：很可能是唯一约束冲突（并发插入），再次确认并返回 409
            if UserDAO.get_user_by_username(username):
                return jsonify({'success': False, 'message': '用户名已存在'}), 409
            # 否则返回通用服务器错误
            return jsonify({'success': False, 'message': '注册失败'}), 500

        # 创建成功，返回 201 并设置会话
        try:
            new_user = UserDAO.get_user_by_username(username)
            if not new_user:
                return jsonify({'success': False, 'message': '注册成功但无法获取用户信息'}), 500

            session_id = str(uuid.uuid4())
            session_store.set(session_id, new_user, ttl_seconds=24 * 3600)

            payload = {
                'success': True,
                'message': '注册成功',
                'session_id': session_id,
                'data': {
                    'user': {
                        'user_id': new_user['user_id'],
                        'username': new_user['username'],
                        'nickname': new_user['nickname'],
                        'avatar': new_user['avatar']
                    }
                }
            }
            resp = make_response(jsonify(payload), 201)
            resp.set_cookie('session_id', session_id, httponly=True, samesite='Lax', max_age=24 * 3600)
            return resp
        except Exception as e:
            # 如果会话保存出错：尝试回滚用户（可选）并返回 500
            try:
                UserDAO.delete_user_by_username(username)
            except Exception:
                pass
            return jsonify({'success': False, 'message': f'注册过程中出现异常: {str(e)}'}), 500

    @app.route('/api/login', methods=['POST'])
    def login():
        """
        用户登录
        Request Body:
            username (str): 用户名
            password (str): 密码
        
        Returns:
            JSON: 登录结果和用户信息
        """
        data = request.get_json()
        username = data.get('username')
        raw_password = data.get('password')

        # 查找用户
        user = UserDAO.get_user_by_username(username)
        password_ok = False
        if user:
            try:
                # 支持 werkzeug 生成的 hash
                password_ok = check_password_hash(user['password'], raw_password)
            except Exception:
                # 兼容老旧 MD5 存储的数据
                password_ok = (user['password'] == hashlib.md5(raw_password.encode()).hexdigest())

        if user and password_ok:
            # 生成会话ID
            session_id = hashlib.md5("{}{}".format(username, datetime.now()).encode()).hexdigest()
            # 存储会话
            session_store.set(session_id, user, ttl_seconds=24*3600)

            payload = {
                'success': True,
                'message': '登录成功',
                'session_id': session_id,
                'user': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'nickname': user['nickname'],
                    'avatar': user['avatar']
                }
            }
            resp = make_response(jsonify(payload))
            resp.set_cookie('session_id', session_id, httponly=True, samesite='Lax', max_age=24*3600)
            return resp
        else:
            return jsonify({
                'success': False,
                'message': '用户名或密码错误'
            }), 401

    @app.route('/api/logout', methods=['POST'])
    def logout():
        """
        用户登出
        Request Headers:
            Authorization: Bearer <session_id>
        """
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            session_id = auth_header.split(' ')[1]
            session_store.delete(session_id)
        
        return jsonify({
            'success': True,
            'message': '登出成功'
        })

    @app.route('/api/current_user', methods=['GET'])
    def current_user():
        """
        获取当前登录用户信息
        Request Headers:
            Authorization: Bearer <session_id>
        """
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            session_id = auth_header.split(' ')[1]
            user = get_user_by_session(session_id)
            if user:
                return jsonify({
                    'success': True,
                    'user': {
                        'user_id': user['user_id'],
                        'username': user['username'],
                        'nickname': user['nickname'],
                        'avatar': user['avatar']
                    }
                })
        
        return jsonify({
            'success': False,
            'message': '请先登录'
        }), 401

    @app.route('/api/posts', methods=['GET'])
    def get_posts():
        """
        获取推荐帖子列表
        支持按标签筛选、搜索和分页

        Query Parameters:
            tag (str, optional): 标签筛选
            q (str, optional): 搜索关键字
            page (int, optional): 页码，默认为1
            limit (int, optional): 每页数量，默认为20

        Returns:
            JSON: 帖子列表
        """
        tag = request.args.get('tag', default=None, type=str)
        search_query = request.args.get('q', default=None, type=str)
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)

        print("接收到tag参数:", tag)
        print("接收到search参数:", search_query)

        # 检查用户是否已登录，用于个性化推荐
        auth_header = request.headers.get('Authorization')
        user = None
        if auth_header and auth_header.startswith('Bearer '):
            session_id = auth_header.split(' ')[1]
            user = get_user_by_session(session_id)

        # 根据参数决定如何获取帖子数据
        if tag and search_query:
            # 如果同时有标签和搜索参数，先按标签筛选再搜索
            print(f"同时使用标签和搜索: tag={tag}, q={search_query}")
            posts_data = PostDAO.get_posts_by_tag(tag)
            search_query_lower = search_query.lower()
            filtered_posts = [
                post for post in posts_data
                if (search_query_lower in post['title'].lower() or
                    search_query_lower in post['content'].lower() or
                    any(search_query_lower in tag_item.lower() for tag_item in post['tags']))  
            ]
        elif tag:
            # 如果只有标签参数，使用标签筛选
            print(f"使用标签筛选: {tag}")
            filtered_posts = RecommendService.get_tag_posts(tag)
        elif search_query:
            # 如果只有搜索参数，使用搜索功能
            print(f"使用搜索功能: {search_query}")
            filtered_posts = RecommendService.get_search_posts(search_query)
        else:
            # 如果没有标签或搜索参数，获取所有帖子
            print("获取所有帖子")
            posts_data = PostDAO.get_all_posts()
            filtered_posts = posts_data

        print(f"筛选后帖子总数: {len(filtered_posts)}")

        # 对filtered_posts进行个性化处理
        personalized_posts = filtered_posts  # 默认为原始筛选结果
        
        # 仅当用户存在且未指定标签或搜索时，应用全局个性化排序；标签/搜索应优先按筛选结果返回
        if user and not tag and not search_query:
            print(f"对用户 {user['user_id']} 应用个性化推荐")
            try:
                personalized_posts = RecommendService.get_personalized_posts(user['user_id'])
                
                # 如果是标签或搜索筛选，需要在个性化推荐结果中进一步筛选
                if tag or search_query:
                    # 在个性化推荐结果中找到符合筛选条件的帖子
                    if tag:
                        personalized_posts = [post for post in personalized_posts if tag in post.get('tags', [])]
                    if search_query:
                        search_query_lower = search_query.lower()
                        personalized_posts = [
                            post for post in personalized_posts
                            if (search_query_lower in post['title'].lower() or
                                search_query_lower in post['content'].lower() or
                                any(search_query_lower in tag_item.lower() for tag_item in post['tags']))
                        ]
                
                # 安全检查：确保个性化结果与筛选结果长度一致（除非是个性化推荐的自然结果）
                print(f"个性化推荐结果数量: {len(personalized_posts)}, 筛选结果数量: {len(filtered_posts)}")
            except Exception as e:
                print(f"个性化推荐过程中发生错误: {e}")
                # 发生错误时回退到原始筛选结果
                personalized_posts = filtered_posts
        else:
            print("未应用个性化推荐，使用原始筛选结果")
        
        # 确定最终帖子列表
        final_posts = personalized_posts if personalized_posts else filtered_posts
        
        print(f"筛选后帖子数量: {len(filtered_posts)}")
        print(f"个性化后帖子数量: {len(personalized_posts)}")
        print(f"最终帖子数量: {len(final_posts)}")

        # 计算偏移量进行分页
        offset = (page - 1) * limit
        paginated_posts = final_posts[offset:offset + limit]

        print(f"分页后帖子数: {len(paginated_posts)}")

        # 为每个帖子添加评论信息
        for post in paginated_posts:
            post_comments = CommentDAO.get_comments_by_post_id(post['post_id'])
            post['comments_list'] = post_comments[:3]  # 只显示前3条评论
            post['comments_count'] = len(post_comments)

        # 只返回需要的字段
        result = []
        for post in paginated_posts:
            result.append({
                'post_id': post['post_id'],
                'title': post['title'],
                'content': post['content'],
                'tags': post['tags'],  # DAO返回的数据已经是Python对象
                'images': post['images'],  # DAO返回的数据已经是Python对象
                'likes': post['likes'],
                'comments': post['comments_count'],
                'collects': post['collects'],
                'publish_time': post['publish_time'],
                'hot_score': post.get('hot_score', 0),
                'comments_list': post.get('comments_list', [])
            })

        print("最终返回帖子数量:", len(result))

        return jsonify({
            'success': True,
            'data': result,
            'count': len(result),
            'has_more': len(final_posts) > offset + limit,
            'total': len(final_posts),  # 添加总数量以便前端知道还有多少数据
            'total_count': len(final_posts)
        })

    @app.route('/api/posts/<int:post_id>', methods=['GET'])
    def get_post_detail(post_id):
        """
        获取单个帖子详情
        """
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({'success': False, 'message': '帖子不存在'}), 404

        # 获取评论
        comments = CommentDAO.get_comments_by_post_id(post_id)

        # 返回帖子详情
        return jsonify({
            'success': True,
            'data': {
                'post_id': post['post_id'],
                'title': post['title'],
                'content': post['content'],
                'tags': post['tags'],
                'images': post['images'],
                'author': post.get('author', {}),
                'publish_time': post['publish_time'],
                'likes': post['likes'],
                'comments': post['comments'],
                'collects': post['collects'],
                'hot_score': post.get('hot_score', 0),
                'comments_list': comments
            }
        })

    @app.route('/api/posts/<int:post_id>/like', methods=['POST'])
    def toggle_post_like(post_id):
        """
        点赞或取消点赞帖子
        """
        # 检查用户登录状态
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({'success': False, 'message': '会话无效'}), 401
        
        # 检查帖子是否存在
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({'success': False, 'message': '帖子不存在'}), 404
        
        # 使用原子化 DAO 在单个事务中完成检查->插入/删除 user_actions -> 更新 posts.likes
        result = UserActionDAO.toggle_like_atomic(user['user_id'], post_id)
        if not result.get('success'):
            return jsonify({'success': False, 'message': result.get('message', '操作失败')}), 500

        # 返回统一响应：包含 liked 与 like_count（兼容前端要求）
        return jsonify({
            'success': True,
            'liked': bool(result.get('liked')),
            'like_count': int(result.get('like_count', 0))
        })

    @app.route('/api/posts/<int:post_id>/collect', methods=['POST'])
    def toggle_collect(post_id):
        """
        收藏/取消收藏帖子
        """
        # 检查用户登录状态
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401

        # 切换收藏状态
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({'success': False, 'message': '帖子不存在'}), 404

        # 这里应该调用一个切换收藏状态的函数
        new_collects = PostDAO.toggle_collect(post_id)
        
        # 记录用户行为
        UserActionDAO.record_action(user['user_id'], post_id, 'collect')

        return jsonify({
            'success': True,
            'collects': new_collects
        })

    @app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
    def add_comment(post_id):
        """
        添加评论
        """
        # 检查用户登录状态
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401

        # 获取评论内容
        data = request.get_json()
        content = data.get('content')

        if not content:
            return jsonify({'success': False, 'message': '评论内容不能为空'}), 400

        # 添加评论
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({'success': False, 'message': '帖子不存在'}), 404

        comment = CommentDAO.add_comment(post_id, user['user_id'], content)

        return jsonify({
            'success': True,
            'comment': comment
        })

    @app.route('/api/recommend/hybrid_ml', methods=['GET'])
    def get_hybrid_ml_recommendations():
        """
        获取基于机器学习的混合推荐
        Query Parameters:
            user_id (int): 用户ID
            top_n (int): 返回前N个推荐，默认为20
        
        Returns:
            JSON: 推荐帖子列表
        """
        user_id = request.args.get('user_id', type=int)
        top_n = request.args.get('top_n', 20, type=int)
        
        # 获取混合推荐结果
        recommendations = RecommendService.get_hybrid_ml_recommendations(user_id, top_n)
        
        # 格式化推荐结果
        formatted_recommendations = []
        for post in recommendations:
            formatted_post = {
                'post_id': post['post_id'],
                'title': post['title'],
                'content': post['content'],
                'tags': post['tags'],
                'images': post['images'],
                'likes': post['likes'],
                'comments': post['comments'],
                'collects': post['collects'],
                'publish_time': post['publish_time'],
                'hours_from_now': post['hours_from_now'] if 'hours_from_now' in post else 0,
                'hot_score': round(post['hot_score'], 2),
                'ml_predict_score': round(post.get('ml_predict_score', 0.0), 3),
                'tag_match_score': round(post.get('tag_match_score', 0.0), 3),
                'hybrid_score': round(post.get('hybrid_score', post.get('hot_score', 0.0)), 3)
            }
            formatted_recommendations.append(formatted_post)
        
        return jsonify({
            'success': True,
            'data': formatted_recommendations,
            'count': len(formatted_recommendations)
        })

    @app.route('/api/recommend', methods=['GET'])
    def recommend_unified():
        """
        统一推荐接口：/api/recommend?type=hot|tag|personalized|hybrid&user_id=&tag=&limit=
        保留向后兼容的老接口。
        """
        rec_type = request.args.get('type', default='hot', type=str)
        user_id = request.args.get('user_id', type=int)
        tag = request.args.get('tag', type=str)
        q = request.args.get('q', type=str)
        limit = request.args.get('limit', default=20, type=int)
        page = request.args.get('page', default=1, type=int)

        # 分页转换
        offset = (page - 1) * limit

        if rec_type == 'hot':
            posts = RecommendService.get_hot_posts(limit)
            return jsonify({'success': True, 'data': posts, 'count': len(posts)})
        elif rec_type == 'tag':
            if not tag:
                return jsonify({'success': False, 'message': '缺少 tag 参数'}), 400
            posts = RecommendService.get_tag_posts(tag, limit)
            return jsonify({'success': True, 'data': posts, 'count': len(posts)})
        elif rec_type == 'personalized':
            if not user_id:
                return jsonify({'success': False, 'message': '缺少 user_id 参数'}), 400
            posts = RecommendService.get_personalized_posts(user_id, limit)
            return jsonify({'success': True, 'data': posts, 'count': len(posts)})
        elif rec_type == 'hybrid':
            posts = RecommendService.get_hybrid_ml_recommendations(user_id, limit)
            return jsonify({'success': True, 'data': posts, 'count': len(posts)})
        else:
            return jsonify({'success': False, 'message': '未知的 type 参数'}), 400

    @app.route('/api/like', methods=['POST'])
    def update_like():
        """
        更新点赞数，并记录用户点赞行为
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        data = request.get_json()
        post_id = data.get('post_id')
        action = data.get('action', 'like')  # 默认为点赞
        
        if not post_id:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 检查帖子是否存在
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({
                'success': False,
                'message': '帖子不存在'
            }), 404

        # 获取当前用户ID
        user_id = user['user_id']
        
        # 检查用户是否已经点赞
        like_record_exists = UserActionDAO.has_user_action(user_id, post_id, 'like')
        
        if action == 'like':
            if not like_record_exists:
                # 添加点赞记录
                success = UserActionDAO.record_action(user_id, post_id, 'like')
                if success:
                    # 更新帖子点赞数
                    PostDAO.update_likes(post_id, 1)
        elif action == 'unlike':
            if like_record_exists:
                # 删除点赞记录
                success = UserActionDAO.remove_action(user_id, post_id, 'like')
                if success:
                    # 更新帖子点赞数
                    PostDAO.update_likes(post_id, -1)
        else:
            return jsonify({
                'success': False,
                'message': '无效的操作类型'
            }), 400

        # 获取最新的点赞数并返回兼容前端的字段
        updated_post = PostDAO.get_post_by_id(post_id)
        like_count = updated_post['likes'] if updated_post else post['likes']
        # 检查当前用户是否已点赞以返回布尔字段
        try:
            liked_now = bool(UserActionDAO.has_user_action(user_id, post_id, 'like'))
        except Exception:
            liked_now = None

        return jsonify({
            'success': True,
            'liked': liked_now,
            'like_count': int(like_count)
        })

    @app.route('/api/collect', methods=['POST'])
    def update_collect():
        """
        更新收藏数，并记录用户收藏行为
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        data = request.get_json()
        post_id = data.get('post_id')
        action = data.get('action', 'collect')  # 默认为收藏
        
        if not post_id:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 检查帖子是否存在
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({
                'success': False,
                'message': '帖子不存在'
            }), 404

        # 获取当前用户ID
        user_id = user['user_id']
        
        # 检查用户是否已经收藏
        collect_record_exists = UserActionDAO.has_user_action(user_id, post_id, 'collect')
        
        if action == 'collect':
            if not collect_record_exists:
                # 添加收藏记录
                success = UserActionDAO.record_action(user_id, post_id, 'collect')
                if success:
                    # 更新帖子收藏数
                    PostDAO.update_collects(post_id, 1)
        elif action == 'uncollect':
            if collect_record_exists:
                # 删除收藏记录
                success = UserActionDAO.remove_action(user_id, post_id, 'collect')
                if success:
                    # 更新帖子收藏数
                    PostDAO.update_collects(post_id, -1)
        else:
            return jsonify({
                'success': False,
                'message': '无效的操作类型'
            }), 400

        # 获取最新的收藏数并返回兼容前端的字段
        updated_post = PostDAO.get_post_by_id(post_id)
        collects = updated_post['collects'] if updated_post else post['collects']
        try:
            collected_now = bool(UserActionDAO.has_user_action(user_id, post_id, 'collect'))
        except Exception:
            collected_now = None

        return jsonify({
            'success': True,
            'collected': collected_now,
            'collects': int(collects)
        })

    @app.route('/api/comments', methods=['GET'])
    def get_comments():
        """
        获取帖子评论列表
        """
        post_id = request.args.get('post_id', type=int)
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)
        
        if not post_id:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        offset = (page - 1) * limit
        comments = CommentDAO.get_comments_by_post_id(post_id, limit, offset)
        
        return jsonify({
            'success': True,
            'data': comments,
            'count': len(comments),
            'has_more': len(comments) == limit  # 如果返回的数量等于limit，则可能还有更多
        })

    @app.route('/api/comments', methods=['POST'])
    def add_comment_v2():
        """
        添加评论，并记录用户评论行为
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        data = request.get_json()
        post_id = data.get('post_id')
        content = data.get('content')
        
        if not content or not post_id:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 检查帖子是否存在
        post = PostDAO.get_post_by_id(post_id)
        if not post:
            return jsonify({
                'success': False,
                'message': '帖子不存在'
            }), 404

        # 获取当前用户ID
        user_id = user['user_id']

        # 使用 DAO 事务化的方法创建评论并更新计数、记录用户行为（已在 DAO 实现事务）
        new_comment = CommentDAO.create_comment(post_id, user_id, content)
        if not new_comment:
            return jsonify({
                'success': False,
                'message': '评论失败'
            }), 500

        return jsonify({
            'success': True,
            'message': '评论成功',
            'comment': new_comment
        })

    @app.route('/api/user/interactions', methods=['GET'])
    def get_user_interactions():
        """
        获取当前用户的交互记录
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        user_id = user['user_id']
        interaction_type = request.args.get('type', type=str)
        
        result = {}
        if not interaction_type or interaction_type == 'like':
            likes = UserActionDAO.get_user_actions(user_id, 'like')
            result['likes'] = likes
        if not interaction_type or interaction_type == 'collect':
            collects = UserActionDAO.get_user_actions(user_id, 'collect')
            result['collects'] = collects
        if not interaction_type or interaction_type == 'comment':
            comments = UserActionDAO.get_user_actions(user_id, 'comment')
            result['comments'] = comments
        
        return jsonify({
            'success': True,
            'data': result
        })

    @app.route('/api/user_actions/<int:user_id>', methods=['GET'])
    def get_user_actions_api(user_id):
        """
        获取用户的所有行为记录
        """
        # 检查用户登录状态
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        
        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user or user['user_id'] != user_id:
            return jsonify({'success': False, 'message': '权限不足'}), 403
        
        # 获取用户行为记录
        actions = UserActionDAO.get_user_actions(user_id)
        
        return jsonify({
            'success': True,
            'actions': actions
        })

    @app.route('/api/recommend/personalized', methods=['GET'])
    def recommend_personalized():
        """
        兼容前端的个性化推荐接口（FT: /api/recommend/personalized）
        Query: user_id, limit
        """
        user_id = request.args.get('user_id', type=int)
        top_n = request.args.get('limit', type=int)

        if not user_id:
            return jsonify({'success': False, 'message': '缺少 user_id'}), 400

        recommendations = RecommendService.get_personalized_posts(user_id, top_n)

        formatted = []
        for post in recommendations:
            formatted.append({
                'post_id': post['post_id'],
                'title': post['title'],
                'content': post['content'],
                'tags': post.get('tags', []),
                'images': post.get('images', []),
                'likes': post.get('likes', 0),
                'comments': post.get('comments', 0),
                'collects': post.get('collects', 0),
                'publish_time': post.get('publish_time'),
                'hot_score': post.get('hot_score', 0)
            })

        return jsonify({'success': True, 'data': formatted, 'count': len(formatted)})

    @app.route('/api/user_history', methods=['GET'])
    def user_history():
        """
        提供给前端的历史记录接口：/api/user_history?action_type=&user_id=&page=&limit=
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'message': '请先登录'}), 401

        session_id = auth_header.split(' ')[1]
        user = get_user_by_session(session_id)
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401

        user_id = request.args.get('user_id', type=int)
        action_type = request.args.get('action_type', type=str)
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)

        if not user_id or user_id != user['user_id']:
            return jsonify({'success': False, 'message': '权限不足'}), 403

        actions = UserActionDAO.get_user_actions(user_id, action_type) if action_type else UserActionDAO.get_user_actions(user_id)

        # 按时间降序已经由 DAO 保证，进行分页并返回对应帖子
        offset = (page - 1) * limit
        page_actions = actions[offset:offset+limit]

        posts = []
        for a in page_actions:
            p = PostDAO.get_post_by_id(a['post_id'])
            if p:
                posts.append(p)

        return jsonify({
            'success': True,
            'data': posts,
            'count': len(posts),
            'has_more': len(actions) > offset + limit
        })
