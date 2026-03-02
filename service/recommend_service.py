"""
推荐服务层
处理各种推荐算法的业务逻辑
"""

import json
import math
from typing import List, Dict, Optional
from database.dao import PostDAO, UserDAO, UserActionDAO, CommentDAO
from recommendation.hot_rank import calculate_hot_score


# 用户画像缓存
_user_profiles_cache = {}

# 创建全局混合推荐器实例，避免重复创建
_global_hybrid_recommender = None


def get_hybrid_recommender():
    """
    获取混合推荐器单例
    """
    global _global_hybrid_recommender
    if _global_hybrid_recommender is None:
        from ml.hybrid_recommender import HybridRecommender
        _global_hybrid_recommender = HybridRecommender()
    return _global_hybrid_recommender


def get_user_profile(user_id: int) -> Dict:
    """
    获取用户画像，带缓存机制
    :param user_id: 用户ID
    :return: 用户画像字典
    """
    global _user_profiles_cache
    
    # 检查缓存
    if user_id in _user_profiles_cache:
        print(f"从缓存获取用户 {user_id} 的画像")
        return _user_profiles_cache[user_id]
    
    print(f"计算用户 {user_id} 的画像")
    
    # 获取用户的历史行为
    user_actions = UserActionDAO.get_user_actions(user_id)
    
    # 获取所有帖子
    all_posts = PostDAO.get_all_posts()
    
    # 创建帖子ID到帖子内容的映射
    post_id_map = {post['post_id']: post for post in all_posts}
    
    # 统计用户喜欢的标签
    tag_scores = {}
    
    # 为不同类型的交互分配不同的权重
    for action in user_actions:
        action_post = post_id_map.get(action['post_id'])
        if action_post:
            tags = action_post.get('tags', [])
            for tag in tags:
                if tag not in tag_scores:
                    tag_scores[tag] = 0
                
                # 根据行为类型给予不同权重，同时考虑时间衰减
                if action['action_type'] == 'like':
                    weight = 1.0
                elif action['action_type'] == 'collect':
                    weight = 2.0
                elif action['action_type'] == 'comment':
                    weight = 3.0
                else:
                    weight = 0.5
                
                # 考虑时间衰减，越近的行为权重越高
                try:
                    import datetime
                    from dateutil.parser import parse
                    action_time = parse(action['created_at']) if isinstance(action['created_at'], str) else action['created_at']
                    now = datetime.datetime.now()
                    days_diff = (now - action_time).days
                    time_decay = max(0.1, 1.0 - days_diff * 0.01)  # 时间衰减因子
                    tag_scores[tag] += weight * time_decay
                except:
                    # 如果解析时间失败，使用固定权重
                    tag_scores[tag] += weight
    
    # 归一化标签分数
    total_score = sum(tag_scores.values())
    if total_score > 0:
        for tag in tag_scores:
            tag_scores[tag] /= total_score
    
    # 缓存用户画像
    _user_profiles_cache[user_id] = tag_scores
    return tag_scores


def update_user_profile_cache(user_id: int):
    """
    更新用户画像缓存
    :param user_id: 用户ID
    """
    global _user_profiles_cache
    # 删除旧的缓存，下次获取时会重新计算
    if user_id in _user_profiles_cache:
        del _user_profiles_cache[user_id]


class RecommendService:
    """推荐服务类"""
    
    @staticmethod
    def get_hot_posts(top_n: int = None) -> List[Dict]:
        """
        获取热门帖子
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :return: 热门帖子列表
        """
        posts = PostDAO.get_all_posts()
        
        # 重新计算热度分数并排序
        posts_with_scores = []
        for post in posts:
            # 更新热度分数
            hot_score = calculate_hot_score(post)
            post['hot_score'] = hot_score
            posts_with_scores.append((post, hot_score))
        
        # 按热度分数排序
        sorted_posts = sorted(posts_with_scores, key=lambda x: x[1], reverse=True)
        sorted_posts_data = [post_data for post_data, score in sorted_posts]
        
        # 如果指定了top_n，则返回前N个
        if top_n:
            return sorted_posts_data[:top_n]
        
        return sorted_posts_data
    
    @staticmethod
    def get_tag_posts(tag: str, top_n: int = None) -> List[Dict]:
        """
        根据标签获取帖子
        :param tag: 标签
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :return: 符合标签的帖子列表
        """
        posts = PostDAO.get_posts_by_tag(tag)
        
        # 重新计算热度分数并排序
        posts_with_scores = []
        for post in posts:
            hot_score = calculate_hot_score(post)
            post['hot_score'] = hot_score
            posts_with_scores.append((post, hot_score))
        
        # 按热度分数排序
        sorted_posts = sorted(posts_with_scores, key=lambda x: x[1], reverse=True)
        sorted_posts_data = [post_data for post_data, score in sorted_posts]
        
        # 如果指定了top_n，则返回前N个
        if top_n:
            return sorted_posts_data[:top_n]
        
        return sorted_posts_data
    
    @staticmethod
    def get_search_posts(query: str, top_n: int = None) -> List[Dict]:
        """
        根据搜索词获取帖子
        :param query: 搜索词
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :return: 符合搜索条件的帖子列表
        """
        posts = PostDAO.get_posts_by_search(query)
        
        # 重新计算热度分数并排序
        posts_with_scores = []
        for post in posts:
            hot_score = calculate_hot_score(post)
            post['hot_score'] = hot_score
            posts_with_scores.append((post, hot_score))
        
        # 按热度分数排序
        sorted_posts = sorted(posts_with_scores, key=lambda x: x[1], reverse=True)
        sorted_posts_data = [post_data for post_data, score in sorted_posts]
        
        # 如果指定了top_n，则返回前N个
        if top_n:
            return sorted_posts_data[:top_n]
        
        return sorted_posts_data
    
    @staticmethod
    def get_posts_with_pagination(page: int = 1, limit: int = 20, tag: str = None, query: str = None) -> Dict:
        """
        分页获取帖子
        :param page: 页码
        :param limit: 每页数量
        :param tag: 标签筛选
        :param query: 搜索词
        :return: 包含帖子列表和分页信息的字典
        """
        offset = (page - 1) * limit
        
        if query:
            # 搜索模式
            posts = PostDAO.get_posts_by_search(query, limit, offset)
            total_posts = len(PostDAO.get_posts_by_search(query))  # 获取总数
        elif tag:
            # 标签模式
            posts = PostDAO.get_posts_by_tag(tag, limit, offset)
            total_posts = len(PostDAO.get_posts_by_tag(tag))  # 获取总数
        else:
            # 全部模式
            posts = PostDAO.get_all_posts(limit, offset)
            total_posts = len(PostDAO.get_all_posts())  # 获取总数
        
        # 重新计算热度分数
        for post in posts:
            hot_score = calculate_hot_score(post)
            post['hot_score'] = hot_score
        
        # 按热度分数排序
        posts.sort(key=lambda x: x['hot_score'], reverse=True)
        
        return {
            'data': posts,
            'count': len(posts),
            'has_more': total_posts > page * limit,
            'total': total_posts
        }
    
    @staticmethod
    def get_personalized_posts(user_id: int, top_n: int = None) -> List[Dict]:
        """
        获取个性化推荐（只负责排序，不进行过滤）
        :param user_id: 用户ID
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :return: 个性化推荐的帖子列表
        """
        print(f"使用个性化推荐算法，用户ID: {user_id}")
        
        # 获取用户信息
        user = UserDAO.get_user_by_id(user_id)
        if not user:
            print(f"用户 {user_id} 不存在，返回热门推荐")
            return RecommendService.get_hot_posts(top_n)
        
        # 获取用户画像
        user_profile = get_user_profile(user_id)
        print(f"用户 {user_id} 的兴趣标签: {list(user_profile.keys())[:10]}")  # 只打印前10个
        
        # 获取所有帖子
        all_posts = PostDAO.get_all_posts()
        
        # 先计算所有帖子的热度并归一化到0-1，以便与用户画像分数（已归一化）融合
        posts_with_hot = []
        hot_scores = []
        for post in all_posts:
            hs = calculate_hot_score(post)
            post['hot_score'] = hs
            posts_with_hot.append((post, hs))
            hot_scores.append(hs)

        # 归一化热度分数
        min_hot = min(hot_scores) if hot_scores else 0.0
        max_hot = max(hot_scores) if hot_scores else 1.0
        hot_range = max_hot - min_hot if max_hot != min_hot else 1.0

        personalized_scores = []
        for post, raw_hot in posts_with_hot:
            hot_norm = (raw_hot - min_hot) / hot_range

            # 基于用户画像计算标签匹配分数（user_profile 已归一化，0-1）
            action_based_score = 0.0
            post_tags = post.get('tags', [])
            for tag in post_tags:
                if tag in user_profile:
                    action_based_score += user_profile[tag]

            # 确保 action_based_score 在 0-1 范围内（可能小于1）
            action_based_score = min(action_based_score, 1.0)

            # 融合：热度占30%，个性化占70%
            final_score = 0.3 * hot_norm + 0.7 * action_based_score
            personalized_scores.append((post, final_score))
        
        # 按个性化分数排序
        sorted_posts = sorted(personalized_scores, key=lambda x: x[1], reverse=True)
        sorted_posts_data = [post_data for post_data, score in sorted_posts]
        
        # 如果指定了top_n，则返回前N个
        if top_n:
            return sorted_posts_data[:top_n]
        
        # 安全检查：如果个性化推荐结果为空，回退到热门推荐
        if not sorted_posts_data:
            print("个性化推荐结果为空，回退到热门推荐")
            return RecommendService.get_hot_posts(top_n)
        
        return sorted_posts_data

    @staticmethod
    def get_hybrid_ml_recommendations(user_id: int, top_n: int = None) -> List[Dict]:
        """
        获取基于机器学习的混合推荐
        :param user_id: 用户ID
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :return: 混合推荐的帖子列表
        """
        print(f"使用混合推荐算法，用户ID: {user_id}")
        hybrid_recommender = get_hybrid_recommender()
        
        if user_id:
            recommendations = hybrid_recommender.recommend_for_user(user_id, top_n)
        else:
            recommendations = hybrid_recommender.recommend_for_guest(top_n)
        
        # 提取推荐的帖子ID列表用于日志
        recommended_post_ids = [post['post_id'] for post in recommendations[:top_n if top_n else len(recommendations)]]
        print(f"用户 {user_id} 的混合推荐帖子ID列表: {recommended_post_ids}")
        
        return recommendations