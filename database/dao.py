"""
数据访问对象(DAO)层
封装对数据库的各种操作
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from .db import get_db_connection
from utils.time_utils import calc_hours_from_now


def safe_json_loads(value, default=None):
    """
    安全解析数据库中存储的 JSON 字符串，支持 NULL/空字符串/非法 JSON。
    返回解析后的对象或 default（默认空 list/dict 由调用方决定）。
    """
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        s = str(value).strip()
        if s == '' or s.lower() == 'null':
            return default
        return json.loads(s)
    except Exception:
        return default


class PostDAO:
    """帖子数据访问对象"""
    
    @staticmethod
    def get_all_posts(limit: int = None, offset: int = None) -> List[Dict]:
        """
        获取所有帖子
        :param limit: 限制返回数量
        :param offset: 偏移量
        :return: 帖子列表
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM posts ORDER BY hot_score DESC"
        params = []
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [PostDAO._row_to_dict(row) for row in rows]
    
    @staticmethod
    def get_posts_by_tag(tag: str, limit: int = None, offset: int = None) -> List[Dict]:
        """
        根据标签获取帖子
        :param tag: 标签
        :param limit: 限制返回数量
        :param offset: 偏移量
        :return: 符合标签的帖子列表
        """
        # 使用 post_tags 关系表进行高效查询
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT p.* FROM posts p
            JOIN post_tags pt ON p.post_id = pt.post_id
            WHERE pt.tag = ?
            ORDER BY p.hot_score DESC
        """
        params = [tag]

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [PostDAO._row_to_dict(row) for row in rows]
    
    @staticmethod
    def get_posts_by_search(query_str: str, limit: int = None, offset: int = None) -> List[Dict]:
        """
        根据搜索词获取帖子
        :param query_str: 搜索词
        :param limit: 限制返回数量
        :param offset: 偏移量
        :return: 符合搜索条件的帖子列表
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        search_pattern = f'%{query_str}%'
        query = """
        SELECT * FROM posts 
        WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
        ORDER BY hot_score DESC
        """
        params = [search_pattern, search_pattern, search_pattern]
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [PostDAO._row_to_dict(row) for row in rows]
    
    @staticmethod
    def get_post_by_id(post_id: int) -> Optional[Dict]:
        """
        根据ID获取帖子
        :param post_id: 帖子ID
        :return: 帖子数据
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return PostDAO._row_to_dict(row)
        return None
    
    @staticmethod
    def toggle_like(post_id: int, increment: int = 1) -> bool:
        """
        切换帖子的点赞状态（增加或减少点赞数）
        :param post_id: 帖子ID
        :param increment: 点赞数增量，+1表示点赞，-1表示取消点赞
        :return: 操作是否成功
        """
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                # 确保不会出现负数
                cursor.execute("SELECT likes FROM posts WHERE post_id = ?", (post_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                current = row['likes'] if row['likes'] is not None else 0
                new_val = max(0, current + increment)
                cursor.execute("UPDATE posts SET likes = ? WHERE post_id = ?", (new_val, post_id))
                return cursor.rowcount > 0
        except Exception as e:
            print(f"切换点赞状态失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            conn.close()
            return False
    
    @staticmethod
    def update_collects(post_id: int, increment: int = 1) -> bool:
        """
        更新帖子收藏数
        :param post_id: 帖子ID
        :param increment: 增量，正数为增加，负数为减少
        :return: 是否更新成功
        """
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT collects FROM posts WHERE post_id = ?", (post_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                current_collects = row['collects'] if row['collects'] is not None else 0
                new_collects = max(0, current_collects + increment)
                cursor.execute("UPDATE posts SET collects = ? WHERE post_id = ?", (new_collects, post_id))
                return cursor.rowcount > 0
        except Exception as e:
            print(f"更新收藏数失败: {e}")
            try:
                conn.rollback()
            except:
                pass
            conn.close()
            return False
    
    @staticmethod
    def update_comments(post_id: int, increment: int = 1) -> bool:
        """
        更新帖子评论数
        :param post_id: 帖子ID
        :param increment: 增量，正数为增加，负数为减少
        :return: 是否更新成功
        """
        conn = get_db_connection()
        try:
            # 获取当前评论数
            cursor = conn.cursor()
            cursor.execute("SELECT comments FROM posts WHERE post_id = ?", (post_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
                
            current_comments = row['comments']
            new_comments = max(0, current_comments + increment)
            
            # 更新评论数
            cursor.execute("UPDATE posts SET comments = ? WHERE post_id = ?", (new_comments, post_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新评论数失败: {e}")
            conn.close()
            return False
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """
        将数据库行转换为字典
        :param row: 数据库行
        :return: 字典格式的帖子数据
        """
        post_dict = {
            'post_id': row['post_id'],
            'title': row['title'],
            'content': row['content'],
            'tags': safe_json_loads(row['tags'], default=[]),
            'images': safe_json_loads(row['images'], default=[]),
            'likes': row['likes'],
            'comments': row['comments'],
            'collects': row['collects'],
            'publish_time': row['publish_time'],
            'hot_score': row['hot_score']
        }
        # 计算发布距今小时数
        post_dict['hours_from_now'] = calc_hours_from_now(row['publish_time'])
        return post_dict


class UserDAO:
    """用户数据访问对象"""
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict]:
        """
        根据用户名获取用户
        :param username: 用户名
        :return: 用户数据
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserDAO._row_to_dict(row)
        return None
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict]:
        """
        根据ID获取用户
        :param user_id: 用户ID
        :return: 用户数据
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserDAO._row_to_dict(row)
        return None
    
    @staticmethod
    def create_user(username: str, password: str, nickname: str, avatar: str = None) -> bool:
        """
        创建新用户
        :param username: 用户名
        :param password: 密码(MD5)
        :param nickname: 昵称
        :param avatar: 头像URL
        :return: 是否创建成功
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, nickname, avatar) VALUES (?, ?, ?, ?)",
                (username, password, nickname, avatar)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 用户名已存在
            conn.close()
            return False

    @staticmethod
    def delete_user_by_username(username: str) -> bool:
        """
        根据用户名删除用户
        :param username: 用户名
        :return: 是否删除成功
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除用户失败: {e}")
            conn.close()
            return False
    
    @staticmethod
    def get_all_users() -> List[Dict]:
        """
        获取所有用户
        :return: 用户列表
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        conn.close()
        
        return [UserDAO._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row) -> Dict:
        """
        将数据库行转换为字典
        :param row: 数据库行
        :return: 字典格式的用户数据
        """
        user_dict = {
            'user_id': row['user_id'],
            'username': row['username'],
            'password': row['password'],
            'nickname': row['nickname'],
            'avatar': row['avatar'],
        }
        # 如果有profile_tags字段，也加入字典，防御性解析
        if 'profile_tags' in row.keys() and row['profile_tags']:
            user_dict['profile_tags'] = safe_json_loads(row['profile_tags'], default=[])
        else:
            user_dict['profile_tags'] = []
        return user_dict


class CommentDAO:
    """评论数据访问对象"""
    
    @staticmethod
    def create_comment(post_id: int, user_id: int, content: str) -> Optional[Dict]:
        """
        创建评论
        :param post_id: 帖子ID
        :param user_id: 用户ID
        :param content: 评论内容
        :return: 创建的评论数据
        """
        # 使用事务：插入评论 -> 更新帖子评论计数 -> 记录用户行为，三步原子执行
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                publish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO comments (post_id, user_id, content, publish_time)
                    VALUES (?, ?, ?, ?)
                """, (post_id, user_id, content, publish_time))

                comment_id = cursor.lastrowid

                # 更新帖子评论计数（防止负数）
                cursor.execute("SELECT comments FROM posts WHERE post_id = ?", (post_id,))
                row_post = cursor.fetchone()
                if row_post:
                    current_comments = row_post['comments'] if row_post['comments'] is not None else 0
                    new_comments = max(0, current_comments + 1)
                    cursor.execute("UPDATE posts SET comments = ? WHERE post_id = ?", (new_comments, post_id))

                # 记录用户行为
                cursor.execute(
                    "INSERT INTO user_actions (user_id, post_id, action_type, action_time) VALUES (?, ?, ?, ?)",
                    (user_id, post_id, 'comment', publish_time)
                )

                # 获取刚刚插入的评论数据
                cursor.execute("""
                    SELECT c.*, u.username, u.nickname, u.avatar
                    FROM comments c
                    JOIN users u ON c.user_id = u.user_id
                    WHERE c.comment_id = ?
                """, (comment_id,))
                row = cursor.fetchone()

            # with conn: 提交成功后返回
            if row:
                return CommentDAO._row_to_dict(row)
            return None
        except Exception as e:
            # with 上下文会在异常时回滚
            print(f"创建评论失败(事务回滚): {e}")
            try:
                conn.rollback()
            except:
                pass
            conn.close()
            return None
    
    @staticmethod
    def get_comments_by_post_id(post_id: int, limit: int = None, offset: int = None) -> List[Dict]:
        """
        根据帖子ID获取评论
        :param post_id: 帖子ID
        :param limit: 限制返回数量
        :param offset: 偏移量
        :return: 评论列表
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT c.*, u.username, u.nickname, u.avatar
            FROM comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.post_id = ?
            ORDER BY c.publish_time DESC
        """
        params = [post_id]
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                query += " OFFSET ?"
                params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [CommentDAO._row_to_dict(row) for row in rows]
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """
        将数据库行转换为字典
        :param row: 数据库行
        :return: 字典格式的评论数据
        """
        comment_dict = {
            'comment_id': row['comment_id'],
            'post_id': row['post_id'],
            'user_id': row['user_id'],
            'username': row['username'],
            'nickname': row['nickname'],
            'avatar': row['avatar'],
            'content': row['content'],
            'publish_time': row['publish_time'],
            'likes': row['likes']
        }
        return comment_dict


class UserActionDAO:
    """用户行为数据访问对象"""
    
    @staticmethod
    def record_action(user_id: int, post_id: int, action_type: str) -> bool:
        """
        记录用户行为
        :param user_id: 用户ID
        :param post_id: 帖子ID
        :param action_type: 行为类型('like', 'collect', 'comment')
        :return: 是否记录成功
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_actions (user_id, post_id, action_type, action_time) VALUES (?, ?, ?, ?)",
                (user_id, post_id, action_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"记录用户行为失败: {e}")
            conn.close()
            return False
    
    @staticmethod
    def remove_action(user_id: int, post_id: int, action_type: str) -> bool:
        """
        移除用户行为记录
        :param user_id: 用户ID
        :param post_id: 帖子ID
        :param action_type: 行为类型('like', 'collect', 'comment')
        :return: 是否移除成功
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_actions WHERE user_id = ? AND post_id = ? AND action_type = ?",
                (user_id, post_id, action_type)
            )
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"移除用户行为记录失败: {e}")
            conn.close()
            return False
    
    @staticmethod
    def get_user_actions(user_id: int, action_type: str = None) -> List[Dict]:
        """
        获取用户的行为记录
        :param user_id: 用户ID
        :param action_type: 行为类型，如果为None则获取所有类型
        :return: 行为记录列表
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if action_type:
            cursor.execute(
                "SELECT * FROM user_actions WHERE user_id = ? AND action_type = ? ORDER BY action_time DESC",
                (user_id, action_type)
            )
        else:
            cursor.execute(
                "SELECT * FROM user_actions WHERE user_id = ? ORDER BY action_time DESC",
                (user_id,)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    @staticmethod
    def has_user_action(user_id: int, post_id: int, action_type: str) -> bool:
        """
        检查用户是否对帖子进行了特定操作
        :param user_id: 用户ID
        :param post_id: 帖子ID
        :param action_type: 行为类型
        :return: 是否存在操作记录
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM user_actions WHERE user_id = ? AND post_id = ? AND action_type = ? LIMIT 1",
            (user_id, post_id, action_type)
        )
        row = cursor.fetchone()
        conn.close()
        
        return row is not None

    @staticmethod
    def toggle_like_atomic(user_id: int, post_id: int) -> dict:
        """
        原子化切换 like 操作：在单个事务（BEGIN IMMEDIATE）中完成检查->插入/删除 user_actions -> 更新 posts.likes。
        返回字典: { 'success': bool, 'liked': bool, 'like_count': int }
        说明：使用 BEGIN IMMEDIATE 获取写锁以避免并发竞态。
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # 获取写锁，防止并发写冲突（SQLite: BEGIN IMMEDIATE 获得写锁）
            cursor.execute('BEGIN IMMEDIATE')

            # 确认帖子存在
            cursor.execute('SELECT likes FROM posts WHERE post_id = ?', (post_id,))
            row_post = cursor.fetchone()
            if not row_post:
                conn.rollback()
                conn.close()
                return {'success': False, 'message': '帖子不存在'}

            current_likes = row_post['likes'] if row_post['likes'] is not None else 0

            # 检查是否已点赞
            cursor.execute(
                "SELECT 1 FROM user_actions WHERE user_id = ? AND post_id = ? AND action_type = 'like' LIMIT 1",
                (user_id, post_id)
            )
            exists = cursor.fetchone() is not None

            if exists:
                # 取消点赞：删除所有相关记录，防止历史重复记录
                cursor.execute(
                    "DELETE FROM user_actions WHERE user_id = ? AND post_id = ? AND action_type = 'like'",
                    (user_id, post_id)
                )

                new_likes = max(0, current_likes - 1)
                cursor.execute("UPDATE posts SET likes = ? WHERE post_id = ?", (new_likes, post_id))
                conn.commit()
                conn.close()
                return {'success': True, 'liked': False, 'like_count': new_likes}
            else:
                # 点赞：插入一条记录（事务内保证幂等性），并增加 likes
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO user_actions (user_id, post_id, action_type, action_time) VALUES (?, ?, 'like', ?)",
                    (user_id, post_id, now)
                )

                new_likes = current_likes + 1
                cursor.execute("UPDATE posts SET likes = ? WHERE post_id = ?", (new_likes, post_id))
                conn.commit()
                conn.close()
                return {'success': True, 'liked': True, 'like_count': new_likes}
        except Exception as e:
            try:
                conn.rollback()
            except:
                pass
            conn.close()
            print(f"toggle_like_atomic 失败: {e}")
            return {'success': False, 'message': str(e)}