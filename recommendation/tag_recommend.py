"""
标签偏好推荐算法
根据用户选择的标签筛选并排序帖子
"""
from .hot_rank import get_hot_posts


def filter_posts_by_tag(posts, tag):
    """
    根据标签筛选帖子
    
    Args:
        posts (list): 帖子列表
        tag (str): 标签
    
    Returns:
        list: 包含指定标签的帖子列表
    """
    filtered_posts = []
    for post in posts:
        # 确保标签是列表格式，然后检查是否包含指定标签
        post_tags = post.get('tags', [])
        if isinstance(post_tags, str):
            post_tags = [post_tags]
        if tag in post_tags:
            filtered_posts.append(post)
    return filtered_posts


def get_tag_posts(posts, tag, top_n=None):
    """
    获取指定标签的热门帖子
    
    Args:
        posts (list): 帖子列表
        tag (str): 标签
        top_n (int, optional): 返回前N个帖子，默认返回全部
    
    Returns:
        list: 按热度排序的指定标签帖子列表
    """
    if not tag:
        # 如果标签为空，返回全部帖子的热门排序
        return get_hot_posts(posts, top_n)
    
    # 首先按标签筛选帖子
    filtered_posts = filter_posts_by_tag(posts, tag)
    
    # 再按热度排序
    hot_posts = get_hot_posts(filtered_posts, top_n)
    
    return hot_posts