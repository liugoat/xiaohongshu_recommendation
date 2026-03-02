"""
互动数据生成器
生成点赞、评论、收藏等数据
"""
import random


def generate_interactions():
    """
    生成互动数据（点赞、评论、收藏）
    
    Returns:
        dict: 包含likes、comments、collects的字典
    """
    # 生成基础点赞数（50-5000）
    likes = random.randint(50, 5000)
    
    # 评论数约为点赞数的5%-20%
    comments_min = int(likes * 0.05)
    comments_max = int(likes * 0.2)
    comments = random.randint(comments_min, comments_max)
    
    # 收藏数约为点赞数的20%-50%
    collects_min = int(likes * 0.2)
    collects_max = int(likes * 0.5)
    collects = random.randint(collects_min, collects_max)
    
    return {
        "likes": likes,
        "comments": comments,
        "collects": collects
    }

class MetricsGenerator:
    """互动数据生成器"""
    
    @staticmethod
    def generate_like_count():
        """
        生成点赞数
        :return: 点赞数（50-5000之间）
        """
        import random
        return random.randint(50, 5000)
    
    @staticmethod
    def generate_comment_count(like_count):
        """
        根据点赞数生成评论数
        :param like_count: 点赞数
        :return: 评论数（约为点赞数的5%-20%）
        """
        import random
        ratio = random.uniform(0.05, 0.2)
        return int(like_count * ratio)
    
    @staticmethod
    def generate_collect_count(like_count):
        """
        根据点赞数生成收藏数
        :param like_count: 点赞数
        :return: 收藏数（约为点赞数的20%-50%）
        """
        import random
        ratio = random.uniform(0.2, 0.5)
        return int(like_count * ratio)
    
    @staticmethod
    def generate_interaction_data():
        """
        生成完整的互动数据
        :return: (点赞数, 评论数, 收藏数)
        """
        likes = MetricsGenerator.generate_like_count()
        comments = MetricsGenerator.generate_comment_count(likes)
        collects = MetricsGenerator.generate_collect_count(likes)
        
        return likes, comments, collects