"""
标签映射器
用于统一帖子标签和用户兴趣标签体系
"""

from typing import List, Dict, Set
import re


class TagMapper:
    """
    标签映射器，用于统一帖子标签和用户兴趣标签
    """
    
    # 定义标签映射规则
    TAG_MAPPING_RULES = {
        # 旅行相关
        '旅行': ['旅游', '出行', '风景', '景点', '自驾游', '国外', '海外', '度假', '旅游攻略', '旅拍'],
        '国外': ['海外', '出国', '境外', '异国', '外国'],
        '风景': ['自然风光', '景色', '景观', '摄影地', '风景照', '户外'],
        
        # 美妆相关
        '护肤': ['保养', '护肤美妆', '护肤步骤', '护肤知识', '护肤产品'],
        '化妆': ['美妆', '彩妆', '妆容', '美妆技巧', '彩妆产品'],
        '面膜': ['面膜护肤', '面膜评测', '面膜推荐', '面膜使用'],
        
        # 穿搭相关
        '穿搭': ['搭配', '服装搭配', '时尚搭配', '衣服搭配', '造型'],
        '时尚': ['潮流', '流行', '时尚圈', '时尚趋势'],
        '衣服': ['服装', '服饰', '衣橱', '衣品'],
        '品牌': ['名牌', '奢侈品牌', '设计师品牌', '品牌推荐'],
        
        # 生活相关
        '美食': ['吃货', '食物', '餐饮', '料理', '烹饪', '甜品', '饮品'],
        '健身': ['运动', '健身运动', '锻炼', '健身计划', '健身器材'],
        '学习': ['教育', '知识', '学习方法', '学习技巧', '自我提升'],
        
        # 数码科技
        '数码': ['数码产品', '电子产品', '数码设备', '电子'],
        '科技': ['科技产品', '科技创新', '技术', '智能'],
    }
    
    # 反向映射：从具体标签映射到通用标签
    REVERSE_MAPPING = {}
    
    @classmethod
    def initialize_reverse_mapping(cls):
        """初始化反向映射"""
        for general_tag, specific_tags in cls.TAG_MAPPING_RULES.items():
            for specific_tag in specific_tags:
                cls.REVERSE_MAPPING[specific_tag] = general_tag
    
    @classmethod
    def map_tags(cls, tags: List[str]) -> List[str]:
        """
        将标签列表映射到标准标签
        :param tags: 原始标签列表
        :return: 映射后的标签列表
        """
        if not hasattr(cls, 'REVERSE_MAPPING') or not cls.REVERSE_MAPPING:
            cls.initialize_reverse_mapping()
        
        mapped_tags = set()
        for tag in tags:
            # 如果标签本身就是标准标签，直接添加
            if tag in cls.TAG_MAPPING_RULES:
                mapped_tags.add(tag)
            # 否则尝试映射到标准标签
            elif tag in cls.REVERSE_MAPPING:
                mapped_tags.add(cls.REVERSE_MAPPING[tag])
            else:
                # 没有映射关系，保持原标签
                mapped_tags.add(tag)
        
        return list(mapped_tags)
    
    @classmethod
    def get_similarity_score(cls, user_tags: List[str], post_tags: List[str]) -> float:
        """
        计算用户兴趣标签与帖子标签的相似度分数
        :param user_tags: 用户兴趣标签
        :param post_tags: 帖子标签
        :return: 相似度分数 (0-1)
        """
        if not user_tags or not post_tags:
            return 0.0
        
        # 映射标签到标准形式
        mapped_user_tags = set(cls.map_tags(user_tags))
        mapped_post_tags = set(cls.map_tags(post_tags))
        
        # 计算交集和并集
        intersection = mapped_user_tags & mapped_post_tags
        union = mapped_user_tags | mapped_post_tags
        
        if len(union) == 0:
            return 0.0
        
        # 使用Jaccard相似度
        jaccard_score = len(intersection) / len(union)
        
        # 计算精确匹配分数（权重更高）
        exact_matches = set(user_tags) & set(post_tags)
        exact_score = len(exact_matches) / max(len(user_tags), 1)  # 避免除零
        
        # 综合分数：Jaccard相似度占70%，精确匹配占30%
        return 0.7 * jaccard_score + 0.3 * exact_score
    
    @classmethod
    def get_detailed_match_info(cls, user_tags: List[str], post_tags: List[str]) -> Dict:
        """
        获取详细的匹配信息
        :param user_tags: 用户兴趣标签
        :param post_tags: 帖子标签
        :return: 包含匹配详情的字典
        """
        if not hasattr(cls, 'REVERSE_MAPPING') or not cls.REVERSE_MAPPING:
            cls.initialize_reverse_mapping()
        
        # 映射标签
        mapped_user_tags = cls.map_tags(user_tags)
        mapped_post_tags = cls.map_tags(post_tags)
        
        # 计算匹配
        exact_matches = list(set(user_tags) & set(post_tags))
        mapped_matches = list(set(mapped_user_tags) & set(mapped_post_tags))
        
        # 找出映射匹配的具体对应关系
        mapping_details = []
        for user_tag in user_tags:
            for post_tag in post_tags:
                if user_tag in cls.REVERSE_MAPPING and cls.REVERSE_MAPPING[user_tag] in mapped_post_tags:
                    mapping_details.append({
                        'user_tag': user_tag,
                        'mapped_to': cls.REVERSE_MAPPING[user_tag],
                        'matched_post_tag': [pt for pt in post_tags if pt in cls.map_tags([pt]) and cls.REVERSE_MAPPING[user_tag] in cls.map_tags([pt])]
                    })
                elif post_tag in cls.REVERSE_MAPPING and cls.REVERSE_MAPPING[post_tag] in mapped_user_tags:
                    mapping_details.append({
                        'post_tag': post_tag,
                        'mapped_to': cls.REVERSE_MAPPING[post_tag],
                        'matched_user_tag': [ut for ut in user_tags if ut in cls.map_tags([ut]) and cls.REVERSE_MAPPING[post_tag] in cls.map_tags([ut])]
                    })
        
        return {
            'original_user_tags': user_tags,
            'original_post_tags': post_tags,
            'mapped_user_tags': mapped_user_tags,
            'mapped_post_tags': mapped_post_tags,
            'exact_matches': exact_matches,
            'mapped_matches': mapped_matches,
            'mapping_details': mapping_details,
            'similarity_score': cls.get_similarity_score(user_tags, post_tags)
        }


# 初始化映射器
TagMapper.initialize_reverse_mapping()