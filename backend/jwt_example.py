import os
import time
import jwt

# 简单 JWT 示例（依赖 pyjwt）
# 安装: pip install PyJWT

JWT_SECRET = os.environ.get('JWT_SECRET', 'change-this-secret-in-prod')
JWT_ALGORITHM = 'HS256'
JWT_EXP_SECONDS = 60 * 60 * 24  # 1 day


def create_jwt(user_id, expires_in=JWT_EXP_SECONDS):
    payload = {
        'sub': str(user_id),
        'iat': int(time.time()),
        'exp': int(time.time()) + int(expires_in)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # pyjwt>=2 returns str, <=1 returns bytes
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


def decode_jwt(token):
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return data
    except Exception:
        return None
