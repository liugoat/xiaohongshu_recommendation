"""
用户画像构建器
基于用户历史行为构建加权兴趣画像
"""

from typing import Dict, List, Tuple
import sqlite3
import json
from collections import defaultdict
from pathlib import Path
import sys

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from database.dao import UserActionDAO, PostDAO


class UserProfiler:
    """
    用户画像构建器，基于用户历史行为构建加权兴趣画像
    """

    # 行为权重定义（相对权重，最终会归一化到0-1区间）
    ACTION_WEIGHTS = {
        'like': 3.0,      # 点赞权重
        'collect': 4.0,   # 收藏权重
        'comment': 5.0,   # 评论权重
        'share': 6.0,     # 分享权重
        'view': 1.0       # 浏览权重
    }

    def __init__(self, db_path: str = None):
        """
        初始化用户画像构建器
        :param db_path: 数据库路径
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'recommend.db'
        self.db_path = db_path
        # 预先导入依赖的DAO类，避免重复导入
        from database.dao import UserDAO
        self.user_dao = UserDAO
        self.user_action_dao = UserActionDAO
        self.post_dao = PostDAO

    def build_weighted_profile(self, user_id: int) -> Dict[str, float]:
        """
        基于用户历史行为构建加权兴趣画像
        :param user_id: 用户ID
        :return: 加权兴趣标签字典 {tag: weight}
        """
        # 获取用户行为
        user_actions = self.user_action_dao.get_user_actions(user_id)
        
        if not user_actions:
            # 如果没有行为数据，返回用户预设的兴趣标签
            user = self.user_dao.get_user_by_id(user_id)
            if user:
                profile_tags = user.get('profile_tags', [])
                return {tag: 1.0 for tag in profile_tags}
            return {}
        
        # 统计标签权重
        tag_weights = defaultdict(float)
        
        for action in user_actions:
            action_type = action['action_type']
            post_id = action['post_id']
            
            # 获取帖子标签
            post = PostDAO.get_post_by_id(post_id)
            if post:
                post_tags = post.get('tags', [])
                
                # 根据行为类型给予不同权重
                weight = self.ACTION_WEIGHTS.get(action_type, 1.0)
                
                # 将权重分配给帖子的所有标签
                for tag in post_tags:
                    tag_weights[tag] += weight
        
        # 归一化到0-1区间
        total_weight = sum(tag_weights.values())
        if total_weight > 0:
            for tag in list(tag_weights.keys()):
                tag_weights[tag] = tag_weights[tag] / total_weight

        return dict(tag_weights)
    
    def get_top_interests(self, user_id: int, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        获取用户前N个最感兴趣的主题
        :param user_id: 用户ID
        :param top_n: 返回前N个兴趣
        :return: [(tag, weight), ...] 按权重排序
        """
        profile = self.build_weighted_profile(user_id)
        sorted_items = sorted(profile.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:top_n]
    
    def get_behavior_summary(self, user_id: int) -> Dict:
        """
        获取用户行为摘要
        :param user_id: 用户ID
        :return: 行为摘要字典
        """
        user_actions = self.user_action_dao.get_user_actions(user_id)
        
        if not user_actions:
            return {
                'total_actions': 0,
                'action_types': {},
                'engaged_posts': 0
            }
        
        action_types = defaultdict(int)
        engaged_post_ids = set()
        
        for action in user_actions:
            action_types[action['action_type']] += 1
            engaged_post_ids.add(action['post_id'])
        
        return {
            'total_actions': len(user_actions),
            'action_types': dict(action_types),
            'engaged_posts': len(engaged_post_ids)
        }


# 创建全局实例
profiler = UserProfiler()