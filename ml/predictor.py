"""
点击预测器
封装机器学习模型的预测功能
"""

import joblib
import numpy as np
from pathlib import Path
from typing import Union, List
import sys

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ml.data_preprocessor import DataPreprocessor


# 全局缓存模型和标准化器
_global_model = None
_global_scaler = None


class ClickPredictor:
    def __init__(self, model_path: str = None, scaler_path: str = None):
        """
        初始化点击预测器
        :param model_path: 模型文件路径
        :param scaler_path: 标准化器文件路径
        """
        if model_path is None:
            model_path = Path(__file__).parent / 'click_model.pkl'
        if scaler_path is None:
            scaler_path = Path(__file__).parent / 'scaler.pkl'
        
        self.model_path = model_path
        self.scaler_path = scaler_path
        # 使用全局变量，避免重复加载
        global _global_model, _global_scaler
        self.model = _global_model
        self.scaler = _global_scaler
        self.model_loaded = (self.model is not None and self.scaler is not None)
        self.preprocessor = DataPreprocessor()
    
    def load_model(self):
        """
        加载训练好的模型和标准化器（仅在未加载时才加载）
        """
        global _global_model, _global_scaler
        
        if self.model is not None and self.scaler is not None:
            print("模型已在内存中，跳过加载")
            self.model_loaded = True
            return True

        try:
            print("正在加载模型...")
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)

            # 更新全局变量
            _global_model = self.model
            _global_scaler = self.scaler

            self.model_loaded = True
            print("模型和标准化器加载成功")
            return True
        except FileNotFoundError as e:
            print(f"模型文件未找到: {e}")
            self.model_loaded = False
            return False
        except Exception as e:
            print(f"加载模型时发生错误: {e}")
            self.model_loaded = False
            return False
    
    def predict(self, feature_vector: Union[np.ndarray, List[float]]) -> float:
        """
        预测点击概率
        :param feature_vector: 特征向量
        :return: 点击概率 (0-1)
        """
        if self.model is None or self.scaler is None:
            # 返回默认中性概率，保证上层不会崩溃
            return 0.5
        
        # 确保输入是numpy数组
        if isinstance(feature_vector, list):
            feature_vector = np.array(feature_vector).reshape(1, -1)
        elif len(feature_vector.shape) == 1:
            feature_vector = feature_vector.reshape(1, -1)
        
        # 标准化特征
        feature_vector_scaled = self.scaler.transform(feature_vector)
        
        # 预测概率
        click_probability = self.model.predict_proba(feature_vector_scaled)[0, 1]
        
        return float(click_probability)
    
    def predict_for_post(self, user_id: int, post: dict) -> float:
        """
        为特定用户和帖子预测点击概率
        :param user_id: 用户ID
        :param post: 帖子数据
        :return: 点击概率 (0-1)
        """
        # 如果模型未加载或预测出错，返回默认概率
        try:
            if self.model is None or self.scaler is None:
                return 0.5

            # 获取特征向量
            feature_vector = self.preprocessor.get_features_for_post(user_id, post)
            # 预测
            return self.predict(feature_vector)
        except Exception as e:
            print(f"predict_for_post 出错，返回默认概率: {e}")
            return 0.5
    
    def batch_predict_for_user(self, user_id: int, posts: List[dict]) -> List[float]:
        """
        为特定用户和多个帖子批量预测点击概率
        :param user_id: 用户ID
        :param posts: 帖子数据列表
        :return: 点击概率列表
        """
        if self.model is None or self.scaler is None:
            # 返回中性概率列表
            return [0.5 for _ in posts]
        
        # 一次性获取用户相关信息，减少数据库查询
        import sqlite3
        import json
        conn = sqlite3.connect(self.preprocessor.db_path)
        cursor = conn.cursor()
        
        # 获取用户兴趣标签
        cursor.execute("SELECT profile_tags FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        user_interests = json.loads(result[0]) if result and result[0] and result[0] != 'null' else []
        
        # 计算用户行为数
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE user_id = ?", (user_id,))
        user_action_count = cursor.fetchone()[0]
        
        conn.close()
        
        # 批量构建特征矩阵
        feature_matrix = []
        for post in posts:
            # 计算标签匹配数和匹配分数
            post_tags = post.get('tags', [])
            tag_match_count = len(set(post_tags) & set(user_interests))
            
            # 计算标签匹配分数
            if len(set(post_tags) | set(user_interests)) == 0:
                tag_match_score = 0.0
            else:
                tag_match_score = len(set(post_tags) & set(user_interests)) / len(set(post_tags) | set(user_interests))
            
            # 计算发布时间到现在的小时数
            hours_from_now = self.preprocessor._calculate_hours_from_now(post.get('publish_time', ''))
            
            # 构建特征向量
            features = np.array([
                post.get('hot_score', 0.0),
                post.get('likes', 0),
                post.get('collects', 0),
                post.get('comments', 0),
                tag_match_count,
                tag_match_score,
                hours_from_now,
                user_action_count
            ])
            
            feature_matrix.append(features)
        
        # 转换为numpy数组
        feature_matrix = np.array(feature_matrix)
        
        # 标准化特征
        feature_matrix_scaled = self.scaler.transform(feature_matrix)
        
        # 批量预测概率
        click_probabilities = self.model.predict_proba(feature_matrix_scaled)[:, 1]
        
        return click_probabilities.tolist()
    
    def batch_predict(self, feature_vectors: np.ndarray) -> List[float]:
        """
        批量预测点击概率
        :param feature_vectors: 特征矩阵
        :return: 点击概率列表
        """
        if self.model is None or self.scaler is None:
            raise ValueError("模型未加载，请先调用 load_model() 方法")
        
        # 标准化特征
        feature_vectors_scaled = self.scaler.transform(feature_vectors)
        
        # 预测概率
        click_probabilities = self.model.predict_proba(feature_vectors_scaled)[:, 1]
        
        return click_probabilities.tolist()