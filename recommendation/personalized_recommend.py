"""
个性化推荐算法
根据用户历史行为和兴趣偏好推荐帖子
"""
import json
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import re

# 融合权重（可调）：行为、热度、多样性。保证加和为1.0
FUSION_WEIGHTS = {
    'behavior': 0.6,
    'hot': 0.3,
    'diversity': 0.1
}


def load_user_interactions():
    """
    从JSON文件加载用户交互数据
    """
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'user_interactions.json')
    if os.path.exists(data_path):
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 返回默认交互数据结构
        return {
            "likes": [],
            "collects": [],
            "comments": []
        }


def normalize_text(text):
    """
    标准化文本，去除多余空格、转换大小写等
    """
    # 转换为小写，去除多余空格
    text = re.sub(r'\s+', ' ', text.lower().strip())
    return text


def calculate_user_profile(user_id, posts):
    """
    根据用户行为计算用户兴趣画像
    :param user_id: 用户ID
    :param posts: 所有帖子数据
    :return: 用户兴趣标签字典
    """
    interactions = load_user_interactions()
    
    # 获取用户的所有交互记录
    user_likes = [item for item in interactions['likes'] if item['user_id'] == user_id]
    user_collects = [item for item in interactions['collects'] if item['user_id'] == user_id]
    user_comments = [item for item in interactions['comments'] if item['user_id'] == user_id]
    
    # 创建帖子ID到帖子内容的映射
    post_id_map = {post['post_id']: post for post in posts}
    
    # 统计用户喜欢的标签
    tag_scores = defaultdict(float)
    
    # 为不同类型的交互分配不同的权重
    for like in user_likes:
        post = post_id_map.get(like['post_id'])
        if post:
            tags = post.get('tags', [])
            for tag in tags:
                # 点赞行为，给予基础权重
                normalized_tag = normalize_text(tag)
                tag_scores[normalized_tag] += 1.0
    
    for collect in user_collects:
        post = post_id_map.get(collect['post_id'])
        if post:
            tags = post.get('tags', [])
            for tag in tags:
                # 收藏行为，给予较高权重
                normalized_tag = normalize_text(tag)
                tag_scores[normalized_tag] += 2.0
    
    for comment in user_comments:
        post = post_id_map.get(comment['post_id'])
        if post:
            tags = post.get('tags', [])
            for tag in tags:
                # 评论行为，给予最高权重
                normalized_tag = normalize_text(tag)
                tag_scores[normalized_tag] += 3.0
    
    # 归一化标签分数
    total_score = sum(tag_scores.values())
    if total_score > 0:
        for tag in tag_scores:
            tag_scores[tag] /= total_score
    
    return dict(tag_scores)


def get_candidate_posts(posts, user_id, user_profile):
    """
    第一阶段：候选集生成修复
    生成推荐候选集，包括热门、标签匹配、用户历史相似帖子
    """
    # 候选集
    candidate_set = set()
    
    # 1. 基础候选集 - 热门帖子（取较多以减少热度偏置）
    from .hot_rank import get_hot_posts
    hot_posts = get_hot_posts(posts, top_n=100)
    for post in hot_posts:
        candidate_set.add(post['post_id'])
    
    # 2. 标签匹配候选集 - 用户兴趣标签匹配的帖子
    if user_profile:
        for post in posts:
            post_tags = [normalize_text(tag) for tag in post.get('tags', [])]
            matched_tags = [tag for tag in post_tags if tag in user_profile]
            if matched_tags:  # 如果有标签匹配
                candidate_set.add(post['post_id'])
    
    # 创建帖子ID到帖子内容的映射
    post_id_map = {post['post_id']: post for post in posts}
    
    # 3. 用户历史交相互似帖子 - 基于用户交互过的帖子的相似性
    interactions = load_user_interactions()
    user_interacted_post_ids = [
        item['post_id'] for item in interactions['likes'] + interactions['collects'] + interactions['comments']
        if item['user_id'] == user_id
    ]
    
    for post in posts:
        if post['post_id'] in user_interacted_post_ids:
            continue  # 跳过已交互的帖子
            
        # 查找标签相似的帖子
        post_tags = [normalize_text(tag) for tag in post.get('tags', [])]
        for interacted_post_id in user_interacted_post_ids:
            if interacted_post_id in post_id_map:
                interacted_post = post_id_map[interacted_post_id]
                
                interacted_tags = [normalize_text(tag) for tag in interacted_post.get('tags', [])]
                
                # 如果当前帖子与用户交互过的帖子有共同标签，则加入候选集
                if set(post_tags) & set(interacted_tags):
                    candidate_set.add(post['post_id'])

    # 4. 为了避免候选集仅集中在热门内容，从长期低热度中随机采样一部分以提升多样性
    import random
    non_hot_posts = [p for p in posts if p['post_id'] not in candidate_set]
    if non_hot_posts:
        sample_size = min(50, max(10, int(len(posts) * 0.05)))
        sampled = random.sample(non_hot_posts, sample_size) if len(non_hot_posts) > sample_size else non_hot_posts
        for p in sampled:
            candidate_set.add(p['post_id'])
    
    # 返回候选集对应的帖子，并标记是否来自非热门采样以表示多样性
    candidates = []
    sampled_ids = {p['post_id'] for p in sampled} if non_hot_posts else set()
    for post in posts:
        if post['post_id'] in candidate_set:
            # 标记多样性来源（默认0），被随机采样的低热度帖子标记为1
            post['_diversity'] = 1 if post['post_id'] in sampled_ids else 0
            candidates.append(post)

    return candidates


def calculate_normalized_scores(posts_with_scores):
    """
    分数归一化函数
    """
    if not posts_with_scores:
        return []
    
    scores = [score for _, score in posts_with_scores]
    min_score = min(scores)
    max_score = max(scores)
    
    if max_score == min_score:
        return [(post, 0.5) for post, _ in posts_with_scores]
    
    normalized_scores = [(score - min_score) / (max_score - min_score) for score in scores]
    return [(posts_with_scores[i][0], normalized_scores[i]) for i in range(len(posts_with_scores))]


def calculate_behavior_score(post, user_profile):
    """
    第三阶段：行为分数计算修复
    计算帖子的行为分数
    """
    post_tags = [normalize_text(tag) for tag in post.get('tags', [])]
    behavior_score = 0.0
    
    # 计算用户标签与帖子标签的匹配分数
    for tag in post_tags:
        if tag in user_profile:
            behavior_score += user_profile[tag]
    
    # 确保行为分数不为0，至少给一个最小值
    if behavior_score == 0 and user_profile:
        # 即使没有直接匹配，也考虑是否有语义相近的标签
        behavior_score = 0.01  # 设置最小值，确保有行为分数
    
    return behavior_score


def calculate_personalized_score(post, user_profile, hot_score):
    """
    计算帖子对特定用户的个性化得分
    :param post: 帖子数据
    :param user_profile: 用户兴趣画像
    :param hot_score: 帖子的基础热度分数
    :return: 个性化得分和相关信息
    """
    # 计算标签匹配
    post_tags = [normalize_text(tag) for tag in post.get('tags', [])]
    matched_tags = [tag for tag in post_tags if tag in user_profile]
    
    # 计算行为分数
    behavior_score = calculate_behavior_score(post, user_profile)
    
    # 第六阶段：调试输出
    print(f"帖子ID: {post['post_id']}, "
          f"热度分数: {hot_score:.4f}, "
          f"行为分数: {behavior_score:.4f}, "
          f"匹配标签: {matched_tags}, "
          f"最终分数: ?")  # 最终分数稍后计算
    
    return hot_score, behavior_score, matched_tags


def get_personalized_posts(posts, user_id, top_n=None):
    """
    获取个性化推荐的帖子列表
    :param posts: 帖子列表
    :param user_id: 用户ID
    :param top_n: 返回前N个帖子，如果为None则返回全部
    :return: 个性化推荐的帖子列表
    """
    # 获取用户兴趣画像
    user_profile = calculate_user_profile(user_id, posts)
    
    if not user_profile:
        # 如果用户没有历史行为，则返回热门帖子
        from .hot_rank import get_hot_posts
        return get_hot_posts(posts, top_n)
    
    # 第一阶段：修复候选集生成
    candidate_posts = get_candidate_posts(posts, user_id, user_profile)
    
    # 计算每个帖子的分数
    posts_with_scores = []
    debug_info = []
    
    for post in candidate_posts:
        # 计算热度分数
        hot_score = calculate_hot_score(post)
        
        # 计算个性化分数
        h_score, b_score, matched_tags = calculate_personalized_score(post, user_profile, hot_score)
        
        posts_with_scores.append((post, h_score, b_score))
        debug_info.append({
            'post_id': post['post_id'],
            'hot_score': h_score,
            'behavior_score': b_score,
            'matched_tags': matched_tags
        })
    
    # 第四阶段：分数归一化修复
    # 分别提取热度分数和行为分数进行归一化
    if posts_with_scores:
        hot_scores = [item[1] for item in posts_with_scores]
        behavior_scores = [item[2] for item in posts_with_scores]
        
        # 归一化热度分数
        if hot_scores:
            min_hot = min(hot_scores)
            max_hot = max(hot_scores)
            if max_hot != min_hot:
                normalized_hot_scores = [(score - min_hot) / (max_hot - min_hot) for score in hot_scores]
            else:
                normalized_hot_scores = [0.5 for _ in hot_scores]
        else:
            normalized_hot_scores = []
        
        # 归一化行为分数
        if behavior_scores:
            min_behavior = min(behavior_scores)
            max_behavior = max(behavior_scores)
            if max_behavior != min_behavior:
                normalized_behavior_scores = [(score - min_behavior) / (max_behavior - min_behavior) for score in behavior_scores]
            else:
                normalized_behavior_scores = [0.5 for _ in behavior_scores]
        else:
            normalized_behavior_scores = []
        
        # 第五阶段：融合排序修复
        final_posts_with_scores = []
        for i in range(len(posts_with_scores)):
            post, h_score, b_score = posts_with_scores[i]
            hot_score_norm = normalized_hot_scores[i] if normalized_hot_scores else 0
            behavior_score_norm = normalized_behavior_scores[i] if normalized_behavior_scores else 0
            
            # 使用融合公式：行为、热度、多样性
            diversity_score = post.get('_diversity', 0)
            w_beh = FUSION_WEIGHTS.get('behavior', 0.6)
            w_hot = FUSION_WEIGHTS.get('hot', 0.3)
            w_div = FUSION_WEIGHTS.get('diversity', 0.1)

            # 最终分数（行为与热度归一化，多样性为二值放大项）
            final_score = (w_beh * behavior_score_norm) + (w_hot * hot_score_norm) + (w_div * diversity_score)
            
            # 更新调试信息
            debug_info[i]['hot_score_norm'] = hot_score_norm
            debug_info[i]['behavior_score_norm'] = behavior_score_norm
            debug_info[i]['final_score'] = final_score
            
            final_posts_with_scores.append((post, final_score))
        
        # 按最终得分降序排序
        sorted_posts = sorted(final_posts_with_scores, key=lambda x: x[1], reverse=True)
        
        # 第六阶段：输出调试信息
        print(f"\n=== 个性化推荐调试信息 (用户ID: {user_id}) ===")
        for info in sorted(debug_info, key=lambda x: x['final_score'], reverse=True)[:10]:  # 只打印前10个
            print(f"帖子ID: {info['post_id']}, "
                  f"热度分: {info['hot_score']:.3f}→{info['hot_score_norm']:.3f}, "
                  f"行为分: {info['behavior_score']:.3f}→{info['behavior_score_norm']:.3f}, "
                  f"匹配标签: {info['matched_tags']}, "
                  f"最终分: {info['final_score']:.3f}")
        print("="*50)
        
        # 提取帖子数据
        sorted_posts_data = [post_data for post_data, score in sorted_posts]
        
        # 如果指定了top_n，则返回前N个
        if top_n:
            return sorted_posts_data[:top_n]
    
        return sorted_posts_data


def calculate_hot_score(post):
    """
    计算帖子热度分数（复用上面的算法）
    :param post: 帖子数据
    :return: 热度分数
    """
    likes = post.get('likes', 0)
    collects = post.get('collects', 0)
    comments = post.get('comments', 0)
    views = post.get('views', 0)  # 假设有浏览量数据
    
    # 如果没有views数据，则使用likes+comments+collects作为基础互动量并限幅
    base_interaction = likes + comments + collects
    est_views = base_interaction * 3
    est_views = max(10, min(100000, int(est_views)))

    engagement_rate = 0.0
    if est_views > 0:
        engagement_rate = (likes + comments + collects) / est_views

    # 时间衰减使用 recommendation.hot_rank 中的指数衰减函数
    publish_time_str = post.get('publish_time', '')
    time_factor = 1.0
    if publish_time_str:
        try:
            publish_time = datetime.strptime(publish_time_str, '%Y-%m-%d %H:%M:%S')
            hours_since_published = (datetime.now() - publish_time).total_seconds() / 3600.0
            from .hot_rank import _time_decay_factor
            time_factor = _time_decay_factor(hours_since_published)
            time_factor = max(0.5, min(1.5, 1.0 / (time_factor + 1e-9)))
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