"""
热门推荐算法
根据帖子的互动数据计算热度分数
"""
from datetime import datetime
import math
import math as _math

# 可配置的时间衰减参数（小时为单位），可在部署时调整
TIME_DECAY_LAMBDA = 0.05  # 指数衰减系数，越大衰减越快


def _time_decay_factor(hours_since_published, lam=TIME_DECAY_LAMBDA):
    """
    指数衰减因子，越新的帖子因子接近1，随时间指数下降。
    f = exp(-lambda * hours)
    """
    try:
        return _math.exp(-lam * max(0.0, hours_since_published))
    except Exception:
        return 1.0


def calculate_hot_score(post):
    """
    计算帖子热度分数
    :param post: 帖子数据
    :return: 热度分数
    """
    likes = post.get('likes', 0)
    collects = post.get('collects', 0)
    comments = post.get('comments', 0)
    # 注意：数据库中没有views字段，这里使用互动总量的倍数来估算并进行限幅，防止低样本导致极端值
    base_interaction = likes + comments + collects
    est_views = base_interaction * 3
    # 限幅：最小估计视图数为10，最大为100000，防止分母过小或过大
    est_views = max(10, min(100000, int(est_views)))

    # 计算互动率
    engagement_rate = 0.0
    if est_views > 0:
        engagement_rate = (likes + comments + collects) / est_views

    # 时间衰减因子
    publish_time_str = post.get('publish_time', '')
    time_factor = 1.0  # 默认值

    time_factor = 1.0
    if publish_time_str:
        try:
            publish_time = datetime.strptime(publish_time_str, '%Y-%m-%d %H:%M:%S')
            hours_since_published = (datetime.now() - publish_time).total_seconds() / 3600.0
            # 指数衰减：f = exp(-lambda * hours)
            time_factor = _time_decay_factor(hours_since_published)
            # 为了让新内容有一定额外提升，将 time_factor 在 [0.5, 1.5] 做缩放
            time_factor = max(0.5, min(1.5, 1.0 / (time_factor + 0.000001)))
        except Exception:
            pass

    # 内容质量评分（基于互动率）
    quality_score = 1.0
    if engagement_rate > 0.15:  # 高互动率
        quality_score = 1.3
    elif engagement_rate > 0.08:  # 中等互动率
        quality_score = 1.1
    elif engagement_rate > 0.03:  # 低互动率
        quality_score = 0.9
    else:  # 极低互动率
        quality_score = 0.7

    # 不同互动类型的权重
    like_weight = 1.0
    comment_weight = 2.0  # 评论通常表示更强的兴趣
    collect_weight = 2.5  # 收藏表示强烈兴趣

    # 计算基础热度分数
    base_score = (likes * like_weight + 
                  comments * comment_weight + 
                  collects * collect_weight)

    # 应用时间因子和质量因子
    final_score = base_score * time_factor * quality_score

    # 对特别高质量的内容给予额外奖励
    if engagement_rate > 0.2 and likes > 50:
        final_score *= 1.1  # 额外10%奖励

    # 如果帖子有多个图片，稍微增加权重（表示内容更丰富）
    images_count = len(post.get('images', []))
    if images_count > 1:
        final_score *= 1.05  # 每多一张图增加5%权重，最多增加20%
        if images_count > 4:
            final_score *= 1.20/1.05  # 最高到20%

    return final_score


def get_hot_posts(posts, top_n=None):
    """
    获取热门帖子列表（保留此函数用于向后兼容）
    :param posts: 帖子列表
    :param top_n: 返回前N个热门帖子，如果为None则返回全部
    :return: 按热度排序的帖子列表
    """
    # 计算每篇帖子的热度分数
    posts_with_score = []
    for post in posts:
        score = calculate_hot_score(post)
        posts_with_score.append((post, score))
    
    # 按热度分数降序排序
    sorted_posts = sorted(posts_with_score, key=lambda x: x[1], reverse=True)
    
    # 提取帖子数据
    sorted_posts_data = [post_data for post_data, score in sorted_posts]
    
    # 如果指定了top_n，则返回前N个
    if top_n:
        return sorted_posts_data[:top_n]
    
    return sorted_posts_data