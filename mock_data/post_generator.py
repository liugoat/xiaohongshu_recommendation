import random

def generate_interactions():
    """
    生成互动数据（点赞、评论、收藏）
    
    Returns:
        dict: 包含点赞、评论、收藏数量的字典
    """
    likes = random.randint(50, 5000)
    # 评论约为点赞数的5%-20%
    comments = int(likes * random.uniform(0.05, 0.2))
    # 收藏约为点赞数的20%-50%
    collects = int(likes * random.uniform(0.2, 0.5))
    
    return {
        'likes': likes,
        'comments': comments,
        'collects': collects
    }
def generate_image_urls(post_id, count):
    """
    生成图片URL列表
    
    Args:
        post_id (int): 帖子ID
        count (int): 图片数量
    
    Returns:
        list: 图片URL列表
    """
    images = []
    for i in range(count):
        # 使用picsum.photos生成随机图片
        url = f"https://picsum.photos/seed/{post_id}_{i}/400/600"
        images.append(url)
    
    return images
import random
import json
from datetime import datetime, timedelta
from .templates import TEMPLATES
from .image_generator import generate_image_urls
from .metrics_generator import generate_interactions


def generate_post(post_id):
    """
    生成单个帖子数据
    
    Args:
        post_id (int): 帖子ID
    
    Returns:
        dict: 包含帖子信息的字典
    """
    # 随机选择一个主题
    theme = random.choice(list(TEMPLATES.keys()))
    theme_data = TEMPLATES[theme]
    
    # 生成标题
    title_template = random.choice(theme_data['titles'])
    title = title_template.format(random.choice(theme_data['keywords']))
    
    # 生成正文（3-6句话，增加内容丰富度）
    content_sentences = random.sample(theme_data['sentences'], random.randint(3, 6))
    content = ' '.join(content_sentences)
    
    # 生成标签（主题标签+2-4个关键词，增加标签多样性）
    num_additional_tags = random.randint(2, 4)
    additional_tags = random.sample(theme_data['keywords'], min(num_additional_tags, len(theme_data['keywords'])))
    tags = [theme] + additional_tags
    
    # 确保标签不重复
    tags = list(set(tags))
    
    # 生成图片URL（1-9张图片，增加图片多样性）
    image_count = random.randint(1, 9)
    images = generate_image_urls(post_id, image_count)
    
    # 生成互动数据
    interactions = generate_interactions()
    likes = interactions['likes']
    comments = interactions['comments']
    collects = interactions['collects']
    
    # 生成发布时间（最近30天内，精确到分钟）
    publish_time = (datetime.now() - timedelta(days=random.randint(0, 30), 
                                              minutes=random.randint(0, 1439))).strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        "post_id": post_id,
        "title": title,
        "content": content,
        "tags": tags,
        "images": images,
        "likes": likes,
        "comments": comments,
        "collects": collects,
        "publish_time": publish_time
    }


def generate_posts(count=100):
    """
    生成多个帖子数据
    
    Args:
        count (int): 生成帖子数量
    
    Returns:
        list: 包含多个帖子信息的列表
    """
    posts = []
    for i in range(1, count + 1):
        post = generate_post(i)
        posts.append(post)
        
        # 每生成100个打印一次进度
        if i % 100 == 0:
            print(f"已生成 {i}/{count} 个帖子...")
            
    return posts


if __name__ == "__main__":
    # 生成2000个帖子数据并保存到文件
    print("开始生成2000条多样化的小红书帖子数据...")
    posts = generate_posts(2000)
    
    data_path = '../../data/mock_posts.json'
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    print(f"成功生成 {len(posts)} 个帖子数据，已保存到 {data_path}")
    
    # 统计各类别帖子数量
    category_count = {}
    for post in posts:
        category = post['tags'][0]  # 第一个标签通常是类别
        category_count[category] = category_count.get(category, 0) + 1
    
    print("\n各类别帖子数量统计:")
    for category, count in category_count.items():
        print(f"- {category}: {count} 个")