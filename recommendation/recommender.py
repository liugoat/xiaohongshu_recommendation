"""
统一推荐接口
提供推荐帖子的功能
"""
from .hot_rank import get_hot_posts
from .tag_recommend import get_tag_posts
from .personalized_recommend import get_personalized_posts


def recommend_posts(posts, tag=None, user_id=None, top_n=None, user_interactions=None, 
                   use_personalization=False):
    """
    推荐帖子的统一接口
    
    Args:
        posts (list): 帖子列表
        tag (str, optional): 指定标签，如果为None则返回热门推荐
        user_id (int, optional): 用户ID，如果提供则返回个性化推荐
        top_n (int, optional): 返回前N个帖子，默认返回全部
        user_interactions (list, optional): 用户交互数据，用于个性化推荐
        use_personalization (bool): 是否使用个性化推荐
    
    Returns:
        list: 推荐的帖子列表
    """
    if tag:
        # 如果指定了标签，返回该标签下的帖子
        filtered_posts = get_tag_posts(posts, tag)
    else:
        # 否则返回全部帖子
        filtered_posts = posts
    
    # 如果需要个性化推荐，由上层服务处理
    if use_personalization and user_interactions and user_id is not None:
        # 不在这里调用个性化推荐，而是返回筛选后的帖子让上层调用个性化排序
        pass
    
    # 如果指定了top_n，则返回前N个
    if top_n and len(filtered_posts) > top_n:
        return filtered_posts[:top_n]
    
    return filtered_posts


class Recommender:
    """推荐系统主类"""
    
    def __init__(self, posts):
        """
        初始化推荐系统
        :param posts: 帖子数据列表
        """
        self.posts = posts
    
    def recommend_posts(self, tag=None, user_id=None, top_n=None, user_interactions=None, 
                       use_personalization=False):
        """
        推荐帖子
        :param tag: 标签，如果为None则返回热门推荐
        :param user_id: 用户ID，如果提供则返回个性化推荐
        :param top_n: 返回前N个帖子，如果为None则返回全部
        :param user_interactions: 用户交互数据，用于个性化推荐
        :param use_personalization: 是否使用个性化推荐
        :return: 推荐的帖子列表
        """
        if use_personalization and user_interactions and user_id is not None:
            # 使用个性化推荐
            if tag:
                # 如果同时指定了标签，先按标签筛选再进行个性化排序
                tag_posts = get_tag_posts(self.posts, tag)
                return get_personalized_posts(tag_posts, user_id, top_n)
            else:
                # 否则返回个性化推荐
                return get_personalized_posts(self.posts, user_id, top_n)
        elif tag:
            # 如果指定了标签，按标签推荐
            return get_tag_posts(self.posts, tag, top_n)
        else:
            # 否则返回热门推荐
            return get_hot_posts(self.posts, top_n)
    
    def get_all_tags(self):
        """
        获取所有标签
        :return: 标签列表
        """
        all_tags = set()
        for post in self.posts:
            for tag in post.get('tags', []):
                all_tags.add(tag)
        return list(all_tags)