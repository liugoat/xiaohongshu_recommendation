"""
图片URL生成器
使用 https://picsum.photos 服务生成随机图片URL
"""
import random


class ImageGenerator:
    """图片生成器"""
    
    @staticmethod
    def generate_image_url(post_id, index=0, width=400, height=600):
        """
        生成图片URL
        :param post_id: 帖子ID
        :param index: 图片索引（同一帖子多图）
        :param width: 图片宽度
        :param height: 图片高度
        :return: 图片URL
        """
        return f"https://picsum.photos/seed/{post_id}_{index}/{width}/{height}"


def generate_image_urls(post_id, count=1):
    """
    为帖子生成图片URL列表
    
    Args:
        post_id (int): 帖子ID
        count (int): 图片数量
    
    Returns:
        list: 包含图片URL的列表
    """
    base_url = "https://picsum.photos/seed"
    image_urls = []
    
    for i in range(count):
        # 使用帖子ID和索引生成唯一的种子值，确保每次生成的图片URL一致
        url = f"{base_url}/{post_id}_{i}/400/600"
        image_urls.append(url)
    
    return image_urls