"""
会话存储抽象：SessionStore
当前实现为内存字典，可后续替换为 Redis 实现而不改路由逻辑。
"""
from datetime import datetime, timedelta
from typing import Optional


class SessionStore:
    def __init__(self):
        # {session_id: {'user': user_dict, 'expires': datetime}}
        self._store = {}

    def set(self, session_id: str, user: dict, ttl_seconds: int = 24*3600):
        self._store[session_id] = {
            'user': user,
            'expires': datetime.now() + timedelta(seconds=ttl_seconds)
        }

    def get(self, session_id: str) -> Optional[dict]:
        entry = self._store.get(session_id)
        if not entry:
            return None
        if datetime.now() >= entry['expires']:
            # 过期则删除
            try:
                del self._store[session_id]
            except KeyError:
                pass
            return None
        return entry['user']

    def delete(self, session_id: str):
        try:
            del self._store[session_id]
        except KeyError:
            pass

    def cleanup(self):
        # 可定期调用清理过期 session
        now = datetime.now()
        to_delete = [sid for sid, e in self._store.items() if now >= e['expires']]
        for sid in to_delete:
            try:
                del self._store[sid]
            except KeyError:
                pass

# 简单内存实例（路由模块可导入并替换为 Redis 实现）
session_store = SessionStore()
