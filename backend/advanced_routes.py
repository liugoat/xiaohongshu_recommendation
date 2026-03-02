import csv
import io
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

from flask import jsonify, request

from database.dao import PostDAO
from database.db import get_db_connection
from recommendation.hot_rank import calculate_hot_score
from .session_store import session_store


STOPWORDS = {
    "的", "了", "和", "是", "在", "也", "就", "都", "很", "一个", "我们", "你们", "他们",
    "这个", "那个", "可以", "真的", "就是", "而且", "但是", "如果", "因为", "所以",
}

POSITIVE_WORDS = {
    "喜欢", "推荐", "不错", "好看", "好用", "优秀", "惊喜", "实用", "值得", "爱了", "满意",
    "开心", "赞", "棒", "舒服", "上头",
}

NEGATIVE_WORDS = {
    "失望", "踩雷", "不好", "难用", "一般", "后悔", "敷衍", "垃圾", "贵", "坑", "差", "无语",
    "难吃", "鸡肋", "烦",
}

TAG_HINTS = {
    "美食": {"吃", "餐", "饭", "饮", "菜", "甜品", "火锅", "咖啡"},
    "旅行": {"旅行", "出行", "景点", "酒店", "机票", "路线", "打卡"},
    "穿搭": {"穿搭", "衣服", "外套", "裙", "鞋", "风格", "搭配"},
    "学习": {"学习", "复习", "笔记", "课程", "考试", "方法", "效率"},
    "护肤": {"护肤", "面膜", "精华", "乳液", "防晒", "敏感肌", "痘"},
    "运动": {"运动", "健身", "跑步", "力量", "减脂", "增肌", "训练"},
    "生活": {"生活", "家居", "收纳", "日常", "通勤", "习惯", "效率"},
}


def _safe_json_loads(value, default):
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        text = str(value).strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _parse_list_field(value):
    parsed = _safe_json_loads(value, None)
    if isinstance(parsed, list):
        return [str(v).strip() for v in parsed if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _tokenize(text):
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text or "")
    return [w.lower() for w in words if w not in STOPWORDS]


def _engagement_score(post):
    return float(post.get("likes", 0)) + 2.0 * float(post.get("comments", 0)) + 1.5 * float(post.get("collects", 0))


def _norm(value, lo, hi):
    if hi <= lo:
        return 0.0
    return (value - lo) / (hi - lo)


def _content_tag_match_score(post):
    tags = post.get("tags", []) or []
    text = f"{post.get('title', '')} {post.get('content', '')}".lower()
    if not tags:
        return 1.0

    hit = 0
    total = 0
    for tag in tags:
        tag_text = str(tag).strip().lower()
        if not tag_text:
            continue
        total += 1
        if tag_text in text:
            hit += 1
            continue
        hints = TAG_HINTS.get(tag_text, set())
        if any(h.lower() in text for h in hints):
            hit += 1
    if total == 0:
        return 1.0
    return hit / total


def _comment_sentiment(text):
    value = str(text or "")
    pos = sum(1 for w in POSITIVE_WORDS if w in value)
    neg = sum(1 for w in NEGATIVE_WORDS if w in value)
    if pos == 0 and neg == 0:
        return "neutral", 0
    if pos >= neg:
        return "positive", pos - neg
    return "negative", pos - neg


def _read_import_payload():
    if request.files.get("file"):
        file = request.files["file"]
        raw = file.read()
        text = raw.decode("utf-8-sig", errors="ignore")
        if file.filename.lower().endswith(".csv"):
            reader = csv.DictReader(io.StringIO(text))
            return [dict(r) for r in reader]
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("posts", [])
        if isinstance(data, list):
            return data
        return []

    data = request.get_json(silent=True) or {}
    if isinstance(data, list):
        return data
    return data.get("posts", [])


def _get_request_user():
    auth_header = request.headers.get("Authorization", "")
    session_id = None
    if auth_header.startswith("Bearer "):
        session_id = auth_header.split(" ", 1)[1].strip()
    if not session_id:
        session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    return session_store.get(session_id)


def _is_admin_user(user):
    if not user:
        return False
    user_type = str(user.get("user_type", "") or "").lower()
    if user_type == "admin":
        return True

    allowed = {
        item.strip() for item in os.getenv("ADMIN_USERNAMES", "admin").split(",")
        if item.strip()
    }
    return str(user.get("username", "") or "") in allowed


def _require_admin():
    user = _get_request_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录管理员账号"}), 401)
    if not _is_admin_user(user):
        return None, (jsonify({"success": False, "message": "无管理端权限"}), 403)
    return user, None


def _insert_posts(posts):
    conn = get_db_connection()
    cursor = conn.cursor()
    imported = 0
    errors = []

    for idx, post in enumerate(posts):
        try:
            title = str(post.get("title", "")).strip()
            content = str(post.get("content", "")).strip()
            if not title or not content:
                raise ValueError("title/content is required")

            tags = _parse_list_field(post.get("tags"))
            images = _parse_list_field(post.get("images"))
            likes = int(post.get("likes", 0) or 0)
            comments = int(post.get("comments", 0) or 0)
            collects = int(post.get("collects", 0) or 0)
            publish_time = str(post.get("publish_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            temp = {
                "likes": likes,
                "comments": comments,
                "collects": collects,
                "hours_from_now": 1.0,
            }
            hot_score = float(calculate_hot_score(temp))

            cursor.execute(
                """
                INSERT INTO posts (title, content, tags, images, likes, comments, collects, publish_time, hot_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    content,
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(images, ensure_ascii=False),
                    likes,
                    comments,
                    collects,
                    publish_time,
                    hot_score,
                ),
            )
            post_id = cursor.lastrowid
            for tag in tags:
                cursor.execute("INSERT INTO post_tags (post_id, tag) VALUES (?, ?)", (post_id, tag))
            imported += 1
        except Exception as exc:
            errors.append({"index": idx, "error": str(exc)})

    conn.commit()
    conn.close()
    return imported, errors


def init_advanced_routes(app):
    @app.route("/api/admin/me", methods=["GET"])
    def admin_me():
        user = _get_request_user()
        if not user:
            return jsonify({"success": False, "is_admin": False, "message": "未登录"}), 401
        return jsonify(
            {
                "success": True,
                "is_admin": _is_admin_user(user),
                "user": {
                    "user_id": user.get("user_id"),
                    "username": user.get("username"),
                    "nickname": user.get("nickname"),
                },
            }
        )

    @app.route("/api/admin/import/posts", methods=["POST"])
    def admin_import_posts():
        _, err = _require_admin()
        if err:
            return err
        posts = _read_import_payload()
        if not posts:
            return jsonify({"success": False, "message": "未检测到可导入的 posts 数据"}), 400

        imported, errors = _insert_posts(posts)
        return jsonify(
            {
                "success": True,
                "imported": imported,
                "failed": len(errors),
                "errors": errors[:20],
            }
        )

    @app.route("/api/dashboard/hot-rank", methods=["GET"])
    def dashboard_hot_rank():
        _, err = _require_admin()
        if err:
            return err
        limit = max(1, min(request.args.get("limit", 10, type=int), 100))
        posts = PostDAO.get_all_posts(limit=limit)
        result = []
        for idx, post in enumerate(posts, 1):
            result.append(
                {
                    "rank": idx,
                    "post_id": post["post_id"],
                    "title": post["title"],
                    "tags": post.get("tags", []),
                    "hot_score": round(float(post.get("hot_score", 0)), 3),
                    "engagement": round(_engagement_score(post), 1),
                }
            )
        return jsonify({"success": True, "data": result})

    @app.route("/api/dashboard/trends", methods=["GET"])
    def dashboard_trends():
        _, err = _require_admin()
        if err:
            return err
        days = max(3, min(request.args.get("days", 14, type=int), 90))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT substr(publish_time, 1, 10) AS day,
                   COUNT(*) AS post_count,
                   SUM(likes + comments * 2 + collects * 1.5) AS engagement
            FROM posts
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
            """,
            (days,),
        )
        rows = cursor.fetchall()
        conn.close()

        data = []
        for row in reversed(rows):
            post_count = int(row["post_count"] or 0)
            engagement = float(row["engagement"] or 0)
            data.append(
                {
                    "day": row["day"],
                    "post_count": post_count,
                    "engagement": round(engagement, 2),
                    "avg_engagement": round(engagement / post_count, 2) if post_count else 0.0,
                }
            )
        return jsonify({"success": True, "data": data})

    @app.route("/api/dashboard/hot-topics", methods=["GET"])
    def dashboard_hot_topics():
        _, err = _require_admin()
        if err:
            return err
        limit = max(1, min(request.args.get("limit", 10, type=int), 100))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT pt.tag,
                   COUNT(*) AS post_count,
                   AVG(p.hot_score) AS avg_hot_score,
                   SUM(p.likes + p.comments * 2 + p.collects * 1.5) AS topic_engagement
            FROM post_tags pt
            JOIN posts p ON p.post_id = pt.post_id
            GROUP BY pt.tag
            ORDER BY topic_engagement DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        result = [
            {
                "tag": row["tag"],
                "post_count": int(row["post_count"] or 0),
                "avg_hot_score": round(float(row["avg_hot_score"] or 0), 3),
                "topic_engagement": round(float(row["topic_engagement"] or 0), 2),
            }
            for row in rows
        ]
        return jsonify({"success": True, "data": result})

    @app.route("/api/analysis/topic-clusters", methods=["GET"])
    def analysis_topic_clusters():
        _, err = _require_admin()
        if err:
            return err
        limit = max(20, min(request.args.get("limit", 200, type=int), 1000))
        posts = PostDAO.get_all_posts(limit=limit)
        if not posts:
            return jsonify({"success": True, "data": []})

        tag_counter = Counter()
        for p in posts:
            tag_counter.update(p.get("tags", []))

        clusters = defaultdict(list)
        for post in posts:
            tags = post.get("tags", []) or []
            if tags:
                key = sorted(tags, key=lambda t: tag_counter[t], reverse=True)[0]
            else:
                key = "未分类"
            clusters[key].append(post)

        data = []
        for i, (label, items) in enumerate(sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True), 1):
            terms = Counter()
            for post in items:
                terms.update(_tokenize(f"{post.get('title', '')} {post.get('content', '')}"))

            sample_posts = [
                {"post_id": p["post_id"], "title": p["title"], "hot_score": round(float(p.get("hot_score", 0)), 3)}
                for p in sorted(items, key=lambda x: x.get("hot_score", 0), reverse=True)[:5]
            ]
            data.append(
                {
                    "cluster_id": i,
                    "label": label,
                    "size": len(items),
                    "keywords": [w for w, _ in terms.most_common(8)],
                    "sample_posts": sample_posts,
                }
            )

        return jsonify({"success": True, "data": data})

    @app.route("/api/recommend/similar", methods=["GET"])
    def recommend_similar():
        _, err = _require_admin()
        if err:
            return err
        post_id = request.args.get("post_id", type=int)
        limit = max(1, min(request.args.get("limit", 10, type=int), 50))
        if not post_id:
            return jsonify({"success": False, "message": "缺少 post_id"}), 400

        target = PostDAO.get_post_by_id(post_id)
        if not target:
            return jsonify({"success": False, "message": "帖子不存在"}), 404

        all_posts = PostDAO.get_all_posts()
        hot_values = [float(p.get("hot_score", 0)) for p in all_posts]
        hot_lo = min(hot_values) if hot_values else 0.0
        hot_hi = max(hot_values) if hot_values else 1.0

        target_tags = set(target.get("tags", []))
        target_tokens = set(_tokenize(f"{target.get('title', '')} {target.get('content', '')}"))
        scored = []

        for post in all_posts:
            if post["post_id"] == post_id:
                continue
            tags = set(post.get("tags", []))
            tokens = set(_tokenize(f"{post.get('title', '')} {post.get('content', '')}"))

            union = target_tags | tags
            tag_sim = len(target_tags & tags) / len(union) if union else 0.0

            token_union = target_tokens | tokens
            token_sim = len(target_tokens & tokens) / len(token_union) if token_union else 0.0

            hot_norm = _norm(float(post.get("hot_score", 0)), hot_lo, hot_hi)
            score = 0.55 * tag_sim + 0.3 * token_sim + 0.15 * hot_norm
            scored.append((score, post))

        scored.sort(key=lambda x: x[0], reverse=True)
        data = [
            {
                "post_id": p["post_id"],
                "title": p["title"],
                "tags": p.get("tags", []),
                "hot_score": round(float(p.get("hot_score", 0)), 3),
                "similarity_score": round(s, 4),
            }
            for s, p in scored[:limit]
        ]
        return jsonify({"success": True, "target_post_id": post_id, "data": data})

    @app.route("/api/assistant/topic-ideas", methods=["GET"])
    def assistant_topic_ideas():
        _, err = _require_admin()
        if err:
            return err
        count = max(1, min(request.args.get("count", 5, type=int), 20))
        posts = PostDAO.get_all_posts()
        if not posts:
            return jsonify({"success": True, "data": []})

        posts_sorted = sorted(posts, key=_engagement_score, reverse=True)
        sample = posts_sorted[: max(20, math.ceil(len(posts_sorted) * 0.2))]

        hour_counter = Counter()
        tag_counter = Counter()
        keyword_counter = Counter()

        for post in sample:
            try:
                hour = datetime.strptime(post.get("publish_time"), "%Y-%m-%d %H:%M:%S").hour
            except Exception:
                hour = 20
            hour_counter.update([hour])
            tag_counter.update(post.get("tags", []))
            keyword_counter.update(_tokenize(f"{post.get('title', '')} {post.get('content', '')}"))

        best_hours = [h for h, _ in hour_counter.most_common(3)] or [20]
        top_tags = [t for t, _ in tag_counter.most_common(max(count, 5))]
        top_words = [w for w, _ in keyword_counter.most_common(max(count * 3, 10))]

        ideas = []
        for i in range(count):
            direction = top_tags[i % len(top_tags)] if top_tags else "生活"
            kw1 = top_words[(i * 2) % len(top_words)] if top_words else "攻略"
            kw2 = top_words[(i * 2 + 1) % len(top_words)] if len(top_words) > 1 else "清单"
            hour = best_hours[i % len(best_hours)]

            ideas.append(
                {
                    "direction": direction,
                    "title_suggestion": f"{direction}避坑指南：{kw1}到{kw2}一次讲清",
                    "publish_time_suggestion": f"建议在 {hour:02d}:00 - {hour:02d}:59 发布",
                    "reasoning": f"该方向在历史高互动样本中表现稳定，关键词“{kw1}/{kw2}”与高热内容共现较多。",
                }
            )

        return jsonify(
            {
                "success": True,
                "basis": {
                    "sample_size": len(sample),
                    "top_hours": best_hours,
                    "top_tags": top_tags[:10],
                },
                "data": ideas,
            }
        )

    @app.route("/api/analysis/comment-sentiment", methods=["GET"])
    def analysis_comment_sentiment():
        _, err = _require_admin()
        if err:
            return err
        post_id = request.args.get("post_id", type=int)
        limit = max(20, min(request.args.get("limit", 200, type=int), 2000))
        conn = get_db_connection()
        cursor = conn.cursor()

        if post_id:
            cursor.execute(
                """
                SELECT c.comment_id, c.post_id, c.content, c.publish_time, p.title, p.tags
                FROM comments c
                JOIN posts p ON p.post_id = c.post_id
                WHERE c.post_id = ?
                ORDER BY c.publish_time DESC
                LIMIT ?
                """,
                (post_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT c.comment_id, c.post_id, c.content, c.publish_time, p.title, p.tags
                FROM comments c
                JOIN posts p ON p.post_id = c.post_id
                ORDER BY c.publish_time DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        conn.close()

        details = []
        summary = {"positive": 0, "negative": 0, "neutral": 0}
        for row in rows:
            label, score = _comment_sentiment(row["content"])
            summary[label] += 1
            details.append(
                {
                    "comment_id": row["comment_id"],
                    "post_id": row["post_id"],
                    "post_title": row["title"],
                    "content": row["content"],
                    "sentiment": label,
                    "score": score,
                }
            )

        total = len(details)
        distribution = {
            k: round(v / total, 4) if total else 0.0
            for k, v in summary.items()
        }
        return jsonify(
            {
                "success": True,
                "summary": summary,
                "distribution": distribution,
                "total": total,
                "data": details,
            }
        )

    @app.route("/api/analysis/tag-audit", methods=["GET"])
    def analysis_tag_audit():
        _, err = _require_admin()
        if err:
            return err
        limit = max(20, min(request.args.get("limit", 200, type=int), 1000))
        posts = PostDAO.get_all_posts(limit=limit)
        findings = []

        for post in posts:
            match_score = _content_tag_match_score(post)
            if match_score >= 0.5:
                continue
            findings.append(
                {
                    "post_id": post["post_id"],
                    "title": post["title"],
                    "tags": post.get("tags", []),
                    "match_score": round(match_score, 3),
                    "suggestion": "标签与正文语义匹配偏低，建议替换为正文中高频主题词。",
                }
            )

        findings.sort(key=lambda x: x["match_score"])
        return jsonify(
            {
                "success": True,
                "count": len(findings),
                "data": findings[:limit],
            }
        )
