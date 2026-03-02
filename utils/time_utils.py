"""
时间处理工具模块
提供时间计算和格式化功能
"""

from datetime import datetime


def calc_hours_from_now(publish_time):
    """
    计算发布时间距离当前时间的小时数
    
    Args:
        publish_time (str or datetime): 发布时间，格式为 'YYYY-MM-DD HH:MM:SS' 或 datetime 对象
    
    Returns:
        float: 距离当前时间的小时数
    """
    if isinstance(publish_time, str):
        # 解析字符串格式的时间
        publish_datetime = datetime.strptime(publish_time, '%Y-%m-%d %H:%M:%S')
    elif isinstance(publish_time, datetime):
        publish_datetime = publish_time
    else:
        raise ValueError("publish_time 必须是字符串格式 'YYYY-MM-DD HH:MM:SS' 或 datetime 对象")
    
    # 获取当前时间
    current_time = datetime.now()
    
    # 计算时间差
    time_diff = current_time - publish_datetime
    
    # 转换为小时
    hours_diff = time_diff.total_seconds() / 3600
    
    return round(hours_diff, 2)