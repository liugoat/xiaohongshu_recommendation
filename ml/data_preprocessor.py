"""
数据预处理器
用于构建机器学习模型的训练样本
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import json
from typing import Tuple, List, Dict, Any


class DataPreprocessor:
    def __init__(self, db_path: str = None):
        """
        初始化数据预处理器
        :param db_path: 数据库路径
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'recommend.db'
        self.db_path = db_path

    def build_training_samples(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        构建训练样本
        :return: (X, y, feature_names) 特征矩阵、标签向量、特征名称列表
        """
        # 连接数据库
        conn = sqlite3.connect(self.db_path)
        
        # 查询用户行为数据
        query = """
        SELECT 
            ua.user_id,
            ua.post_id,
            ua.action_type,
            p.hot_score,
            p.likes,
            p.collects,
            p.comments,
            p.publish_time,
            p.tags as post_tags,
            u.profile_tags
        FROM user_actions ua
        INNER JOIN posts p ON ua.post_id = p.post_id
        INNER JOIN users u ON ua.user_id = u.user_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # 计算额外特征
        df['hours_from_now'] = df['publish_time'].apply(self._calculate_hours_from_now)
        
        # 处理用户标签
        df['user_interests'] = df['profile_tags'].apply(lambda x: json.loads(x) if x and x != 'null' else [])
        df['post_tags'] = df['post_tags'].apply(lambda x: json.loads(x) if x and x != 'null' else [])
        
        # 计算标签匹配数
        df['tag_match_count'] = df.apply(self._calculate_tag_match_count, axis=1)
        
        # 计算标签匹配分数（Jaccard相似度）
        df['tag_match_score'] = df.apply(self._calculate_tag_match_score, axis=1)
        
        # 统计每个用户的行为次数
        user_action_counts = df.groupby('user_id')['action_type'].count().to_dict()
        df['user_action_count'] = df['user_id'].map(user_action_counts)
        
        # 构建特征矩阵
        feature_cols = [
            'hot_score', 
            'likes', 
            'collects', 
            'comments', 
            'tag_match_count', 
            'tag_match_score',  # 新增标签匹配分数特征
            'hours_from_now', 
            'user_action_count'
        ]
        
        X = df[feature_cols].fillna(0).values
        y = df['action_type'].apply(lambda x: 1 if x in ['like', 'collect'] else 0).values
        
        return X, y, feature_cols

    def _calculate_hours_from_now(self, publish_time: str) -> float:
        """
        计算发布到现在的时间（小时）
        """
        from datetime import datetime
        try:
            publish_dt = datetime.strptime(publish_time, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            diff = now - publish_dt
            return diff.total_seconds() / 3600
        except:
            return 0.0

    def _calculate_tag_match_count(self, row: pd.Series) -> int:
        """
        计算标签匹配数
        """
        try:
            post_tags = row['post_tags'] if isinstance(row['post_tags'], list) else []
            user_interests = row['user_interests'] if isinstance(row['user_interests'], list) else []
            if not post_tags or not user_interests:
                return 0
            return len(set(post_tags) & set(user_interests))
        except:
            return 0

    def _calculate_tag_match_score(self, row: pd.Series) -> float:
        """
        计算标签匹配分数（Jaccard相似度）
        """
        try:
            post_tags = row['post_tags'] if isinstance(row['post_tags'], list) else []
            user_interests = row['user_interests'] if isinstance(row['user_interests'], list) else []
            if not post_tags or not user_interests:
                return 0.0
            
            intersection = len(set(post_tags) & set(user_interests))
            union = len(set(post_tags) | set(user_interests))
            
            if union == 0:
                return 0.0
            
            return intersection / union
        except:
            return 0.0

    def get_features_for_post(self, user_id: int, post: Dict[str, Any]) -> np.ndarray:
        """
        为单个帖子构建特征向量
        :param user_id: 用户ID
        :param post: 帖子数据
        :return: 特征向量
        """
        # 获取用户信息和行为统计（一次性获取所有需要的信息）
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取用户兴趣标签
        cursor.execute("SELECT profile_tags FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        user_interests = json.loads(result[0]) if result and result[0] and result[0] != 'null' else []
        
        # 计算用户行为数
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE user_id = ?", (user_id,))
        user_action_count = cursor.fetchone()[0]
        
        conn.close()
        
        # 计算标签匹配数和匹配分数
        post_tags = post.get('tags', [])
        tag_match_count = len(set(post_tags) & set(user_interests))
        
        # 计算标签匹配分数
        if len(set(post_tags) | set(user_interests)) == 0:
            tag_match_score = 0.0
        else:
            tag_match_score = len(set(post_tags) & set(user_interests)) / len(set(post_tags) | set(user_interests))
        
        # 计算发布时间到现在的小时数
        hours_from_now = self._calculate_hours_from_now(post.get('publish_time', ''))
        
        # 构建特征向量
        features = np.array([
            post.get('hot_score', 0.0),
            post.get('likes', 0),
            post.get('collects', 0),
            post.get('comments', 0),
            tag_match_count,
            tag_match_score,  # 新增标签匹配分数
            hours_from_now,
            user_action_count
        ])
        
        return features.reshape(1, -1)