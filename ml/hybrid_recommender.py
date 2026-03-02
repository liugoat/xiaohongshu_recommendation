"""
混合推荐器
结合热度评分、标签匹配和机器学习预测的混合推荐算法
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from pathlib import Path
import sys
from functools import lru_cache

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ml.predictor import ClickPredictor
from ml.tag_mapper import TagMapper
from ml.user_profiler import profiler as user_profiler
from database.dao import PostDAO, UserDAO
from recommendation.hot_rank import calculate_hot_score


class HybridRecommender:
    # 类级别的模型实例，确保只加载一次
    _click_predictor_instance = None

    def __init__(self):
        """
        初始化混合推荐器
        """
        # 使用类级别的实例，避免重复加载
        if HybridRecommender._click_predictor_instance is None:
            HybridRecommender._click_predictor_instance = ClickPredictor()
            loaded = HybridRecommender._click_predictor_instance.load_model()
            if not loaded:
                print("Warning: ClickPredictor 未能加载模型，将使用降级默认分数")
        
        self.click_predictor = HybridRecommender._click_predictor_instance
        self.tag_mapper = TagMapper
    
    def normalize_scores(self, scores: List[float]) -> List[float]:
        """
        标准化分数到0-1范围
        """
        if not scores:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [0.5 for _ in scores]
        
        return [(score - min_score) / (max_score - min_score) for score in scores]
    
    def calculate_enhanced_tag_match_score(self, user_id: int, post_tags: List[str]) -> Tuple[float, Dict]:
        """
        计算增强的标签匹配分数，包含用户行为权重
        :param user_id: 用户ID
        :param post_tags: 帖子标签
        :return: (匹配分数, 详细匹配信息)
        """
        # 获取用户加权兴趣
        user_weighted_interests = user_profiler.build_weighted_profile(user_id)
        
        if not user_weighted_interests:
            # 如果没有行为数据，使用用户预设兴趣
            user = UserDAO.get_user_by_id(user_id)
            if user:
                user_tags = user.get('profile_tags', [])
                user_weighted_interests = {tag: 1.0 for tag in user_tags}
            else:
                return 0.0, {}
        
        # 计算匹配分数
        match_score = 0.0
        match_details = {
            'matched_tags': [],
            'weights': [],
            'total_weight': 0.0
        }
        
        for post_tag in post_tags:
            # 检查直接匹配
            if post_tag in user_weighted_interests:
                weight = user_weighted_interests[post_tag]
                match_score += weight
                match_details['matched_tags'].append(post_tag)
                match_details['weights'].append(weight)
                match_details['total_weight'] += weight
            
            # 检查映射匹配
            mapped_tags = self.tag_mapper.map_tags([post_tag])
            for mapped_tag in mapped_tags:
                if mapped_tag in user_weighted_interests:
                    weight = user_weighted_interests[mapped_tag] * 0.5  # 映射匹配权重减半
                    match_score += weight
                    match_details['matched_tags'].append(f"{post_tag}(映射)")
                    match_details['weights'].append(weight)
                    match_details['total_weight'] += weight
        
        # 归一化分数（可选）
        max_possible_score = sum(user_weighted_interests.values())
        if max_possible_score > 0:
            match_score = match_score / max_possible_score
        
        return min(match_score, 1.0), match_details
    
    def recommend_for_user(self, user_id: int, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        为特定用户生成混合推荐
        :param user_id: 用户ID
        :param top_n: 返回前N个推荐
        :return: 推荐帖子列表
        """
        # 获取用户信息
        user = UserDAO.get_user_by_id(user_id)
        if not user:
            # 如果用户不存在，返回热门推荐
            from service.recommend_service import RecommendService
            return RecommendService.get_hot_posts(top_n)
        
        # 获取用户加权兴趣标签
        user_weighted_interests = user_profiler.build_weighted_profile(user_id)
        user_tags = list(user_weighted_interests.keys()) if user_weighted_interests else user.get('profile_tags', [])
        
        # 获取所有帖子（先获取有限数量的热门帖子，避免处理所有2000个）
        all_posts = PostDAO.get_all_posts()
        
        # 为了性能，我们只对一部分最有可能相关的帖子进行深度计算
        # 首先按热度筛选出前500个帖子
        if len(all_posts) > 500:
            # 先按热度分数排序，只取前500个
            posts_with_hot_score = []
            for post in all_posts:
                from recommendation.hot_rank import calculate_hot_score
                hot_score = calculate_hot_score(post)
                post['hot_score'] = hot_score
                posts_with_hot_score.append((post, hot_score))
            
            # 按热度分数排序，取前500个
            sorted_posts = sorted(posts_with_hot_score, key=lambda x: x[1], reverse=True)
            selected_posts = [post_data for post_data, score in sorted_posts[:500]]
        else:
            selected_posts = all_posts
        
        # 计算各项分数
        hot_scores = [post.get('hot_score', 0.0) for post in selected_posts]
        normalized_hot_scores = self.normalize_scores(hot_scores)
        
        tag_match_scores = []
        tag_match_details = []

        # 先计算 tag match（本地快速计算）
        for post in selected_posts:
            tags = post.get('tags', [])
            tag_score, match_detail = self.calculate_enhanced_tag_match_score(user_id, tags)
            tag_match_scores.append(tag_score)
            tag_match_details.append(match_detail)

        # 批量 ML 预测（降级处理）
        try:
            if self.click_predictor is None or not getattr(self.click_predictor, 'model_loaded', False):
                ml_predict_scores = [0.5 for _ in selected_posts]
            else:
                ml_predict_scores = self.click_predictor.batch_predict_for_user(user_id, selected_posts)
        except Exception as e:
            print(f"批量 ML 预测失败，使用默认概率: {e}")
            ml_predict_scores = [0.5 for _ in selected_posts]
        
        # 计算最终混合分数 - 使用建议的权重
        final_scores = []
        for i in range(len(selected_posts)):
            final_score = (
                0.25 * normalized_hot_scores[i] +    # 热度分权重25%
                0.45 * tag_match_scores[i] +         # 标签匹配权重45%
                0.30 * ml_predict_scores[i]          # ML预测权重30%
            )
            final_scores.append(final_score)
        
        # 添加分数到帖子数据
        for i, post in enumerate(selected_posts):
            post['hybrid_score'] = final_scores[i]
            post['ml_predict_score'] = ml_predict_scores[i]
            post['tag_match_score'] = tag_match_scores[i]
            post['tag_match_details'] = tag_match_details[i]
            post['normalized_hot_score'] = normalized_hot_scores[i]
        
        # 按混合分数排序
        sorted_posts = sorted(selected_posts, key=lambda x: x['hybrid_score'], reverse=True)
        
        # 返回前N个
        return sorted_posts[:top_n] if top_n else sorted_posts
    
    def recommend_for_guest(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        为访客生成推荐（无用户ID时）
        :param top_n: 返回前N个推荐
        :return: 推荐帖子列表
        """
        # 获取热门帖子
        from service.recommend_service import RecommendService
        posts = RecommendService.get_hot_posts(top_n)
        
        # 为访客计算混合分数（不使用用户相关特征）
        for post in posts:
            # 仅使用热度分数作为基础
            hot_score = post.get('hot_score', 0.0)
            normalized_hot_score = hot_score / (max([p.get('hot_score', 0.0) for p in posts]) + 1e-8)  # 防止除零
            
            # 使用默认的ML预测分数
            post['ml_predict_score'] = 0.5
            post['tag_match_score'] = 0.0  # 访客无标签匹配
            post['normalized_hot_score'] = normalized_hot_score
            post['hybrid_score'] = 0.25 * normalized_hot_score + 0.45 * 0.0 + 0.30 * 0.5  # 调整后的权重
        
        return posts