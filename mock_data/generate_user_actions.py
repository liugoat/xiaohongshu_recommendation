"""
模拟用户行为数据生成模块
为推荐系统和机器学习提供训练数据支持
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import os


class UserActionsGenerator:
    def __init__(self, db_path=None):
        """
        初始化用户行为生成器
        :param db_path: 数据库路径
        """
        if db_path is None:
            db_path = os.path.join(Path(__file__).parent.parent, 'recommend.db')
        self.db_path = db_path
        
        # 定义用户类型及其兴趣标签
        self.user_types = [
            {"type": "美妆爱好者", "tags": ["美妆", "护肤", "口红", "化妆", "面膜", "卸妆"]},
            {"type": "穿搭达人", "tags": ["穿搭", "时尚", "衣服", "搭配", "潮流", "品牌"]},
            {"type": "美食探店", "tags": ["美食", "探店", "餐厅", "烘焙", "日料", "火锅"]},
            {"type": "旅行摄影师", "tags": ["旅行", "摄影", "风景", "酒店", "攻略", "国外"]},
            {"type": "健身运动", "tags": ["健身", "运动", "瑜伽", "跑步", "训练", "饮食"]},
            {"type": "数码科技", "tags": ["数码", "手机", "电脑", "评测", "新品", "科技"]},
            {"type": "学习成长", "tags": ["学习", "读书", "职场", "技能", "效率", "时间管理"]},
            {"type": "家居生活", "tags": ["家居", "装修", "收纳", "厨房", "绿植", "手工"]}
        ]
        
        # 定义行为类型及其相对概率
        self.action_probabilities = {
            'view': 0.7,      # 70% 视图
            'like': 0.2,      # 20% 点赞
            'collect': 0.08,  # 8% 收藏
            'comment': 0.02   # 2% 评论
        }

    def get_posts(self):
        """
        从数据库获取所有帖子数据
        :return: 帖子列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT post_id, tags FROM posts")
        rows = cursor.fetchall()
        
        posts = []
        for row in rows:
            post = {
                'post_id': row[0],
                'tags': json.loads(row[1])
            }
            posts.append(post)
        
        conn.close()
        return posts

    def get_existing_users(self):
        """
        获取现有的用户数据
        :return: 用户列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        
        user_ids = [row[0] for row in rows]
        conn.close()
        return user_ids

    def generate_users(self, count=30):
        """
        生成模拟用户数据
        :param count: 生成用户数量
        :return: 生成的用户列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先删除所有模拟用户（包含用户名以"sim_user_"开头的用户）
        cursor.execute("DELETE FROM users WHERE username LIKE 'sim_user_%'")
        cursor.execute("DELETE FROM user_actions WHERE user_id IN (SELECT user_id FROM users WHERE username LIKE 'sim_user_%')")
        
        users = []
        for i in range(count):
            user_type_obj = random.choice(self.user_types)
            user_type = user_type_obj['type']
            user_interests = random.sample(
                user_type_obj['tags'], 
                min(3, len(user_type_obj['tags']))  # 每个用户至少有3个兴趣标签
            )
            
            username = f"sim_user_{i+1:03d}"
            nickname = f"模拟用户{i+1:03d}"
            avatar = f"https://via.placeholder.com/40x40/ff2a68/ffffff?text={nickname[0]}"
            password = f"e10adc3949ba59abbe56e057f20f883e"  # 123456的MD5
            
            cursor.execute("""
                INSERT INTO users (username, password, nickname, avatar, profile_tags, user_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username, 
                password, 
                nickname, 
                avatar, 
                json.dumps(user_interests), 
                user_type
            ))
            
            # 获取新插入用户的ID
            new_user_id = cursor.lastrowid
            
            users.append({
                'user_id': new_user_id,
                'username': username,
                'interests': user_interests,
                'user_type': user_type
            })
        
        conn.commit()
        conn.close()
        print(f"成功生成 {len(users)} 个模拟用户")
        return users

    def calculate_tag_match_score(self, user_interests, post_tags):
        """
        计算用户兴趣标签与帖子标签的匹配度
        :param user_interests: 用户兴趣标签列表
        :param post_tags: 帖子标签列表
        :return: 匹配度分数 (0-1)
        """
        if not user_interests or not post_tags:
            return 0.0
        
        matched_count = len(set(user_interests) & set(post_tags))
        total_interests = len(user_interests)
        
        return matched_count / total_interests if total_interests > 0 else 0.0

    def generate_user_actions(self, user_count=30, actions_per_user=(30, 100)):
        """
        生成用户行为数据
        :param user_count: 用户数量
        :param actions_per_user: 每个用户的行为数量范围 (min, max)
        """
        # 获取帖子数据
        posts = self.get_posts()
        if not posts:
            print("没有找到帖子数据，无法生成用户行为")
            return
        
        # 生成用户
        users = self.generate_users(user_count)
        
        total_actions = 0
        for user in users:
            # 确定该用户要产生的行为数量
            min_actions, max_actions = actions_per_user
            action_count = random.randint(min_actions, max_actions)
            
            # 为用户生成行为数据
            for _ in range(action_count):
                # 随机选择一个帖子
                post = random.choice(posts)
                
                # 计算标签匹配度，影响行为概率
                match_score = self.calculate_tag_match_score(user['interests'], post['tags'])
                
                # 根据匹配度调整行为概率
                adjusted_probs = {}
                base_sum = sum(self.action_probabilities.values())
                for action, prob in self.action_probabilities.items():
                    # 匹配度越高，行为概率越大
                    adjusted_probs[action] = prob * (0.5 + 0.5 * match_score)
                
                # 归一化概率
                total_prob = sum(adjusted_probs.values())
                if total_prob > 0:
                    for action in adjusted_probs:
                        adjusted_probs[action] /= total_prob
                else:
                    # 如果调整后概率为0，则使用原始概率
                    adjusted_probs = self.action_probabilities.copy()
                
                # 根据概率选择行为类型
                action_type = random.choices(
                    list(adjusted_probs.keys()), 
                    weights=list(adjusted_probs.values())
                )[0]
                
                # 生成行为时间（过去1-30天内的随机时间）
                days_ago = random.randint(1, 30)
                hours_ago = random.randint(0, 23)
                mins_ago = random.randint(0, 59)
                
                action_time = datetime.now() - timedelta(
                    days=days_ago, 
                    hours=hours_ago, 
                    minutes=mins_ago
                )
                action_time_str = action_time.strftime('%Y-%m-%d %H:%M:%S')
                
                # 插入行为记录
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO user_actions (user_id, post_id, action_type, action_time)
                    VALUES (?, ?, ?, ?)
                """, (user['user_id'], post['post_id'], action_type, action_time_str))
                
                conn.commit()
                conn.close()
                
                total_actions += 1
        
        print(f"成功生成 {total_actions} 条用户行为记录")
        return total_actions

    def generate(self, user_count=30, actions_per_user=(30, 100)):
        """
        生成完整的用户行为数据
        :param user_count: 用户数量
        :param actions_per_user: 每个用户的行为数量范围
        """
        print("开始生成模拟用户行为数据...")
        total_actions = self.generate_user_actions(user_count, actions_per_user)
        
        # 统计生成的数据
        self.print_statistics()
        
        print("用户行为数据生成完成!")
        return total_actions

    def print_statistics(self):
        """
        打印数据统计信息
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 统计新生成的用户数量（用户名以"sim_user_"开头的用户）
        cursor.execute("SELECT COUNT(*) FROM users WHERE username LIKE 'sim_user_%'")
        user_count = cursor.fetchone()[0]
        
        # 统计新生成的行为数量（用户为模拟用户）
        cursor.execute("SELECT COUNT(*) FROM user_actions WHERE user_id IN (SELECT user_id FROM users WHERE username LIKE 'sim_user_%')")
        action_count = cursor.fetchone()[0]
        
        # 按行为类型统计
        cursor.execute("""
            SELECT action_type, COUNT(*) 
            FROM user_actions 
            WHERE user_id IN (SELECT user_id FROM users WHERE username LIKE 'sim_user_%')
            GROUP BY action_type
        """)
        action_stats = cursor.fetchall()
        
        # 按用户类型统计
        cursor.execute("""
            SELECT user_type, COUNT(*) 
            FROM users 
            WHERE username LIKE 'sim_user_%'
            GROUP BY user_type
        """)
        user_type_stats = cursor.fetchall()
        
        conn.close()
        
        print("\n=== 数据统计 ===")
        print(f"生成用户数量: {user_count}")
        print(f"生成行为数量: {action_count}")
        print("\n行为类型分布:")
        for action_type, count in action_stats:
            print(f"  {action_type}: {count} ({count/action_count*100:.2f}%)")
        print("\n用户类型分布:")
        for user_type, count in user_type_stats:
            print(f"  {user_type}: {count}")


if __name__ == "__main__":
    # 设置随机种子以确保可重复性
    random.seed(42)
    
    generator = UserActionsGenerator()
    generator.generate(user_count=35, actions_per_user=(30, 100))