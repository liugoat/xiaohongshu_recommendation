# 小红书推荐系统（Flask + SQLite）

一个用于演示内容推荐、互动行为与数据分析的轻量全栈项目。

## 1. 项目能力

- 前台信息流：帖子列表、标签筛选、搜索、详情、点赞、收藏、评论
- 登录注册：基于会话（`session_id`）
- 推荐能力：热门推荐、个性化推荐、相似笔记推荐
- 管理端：数据导入、数据看板、主题聚类、AI 选题助手、评论情感分析、标签匹配审计

## 2. 环境要求

- Python 3.8+
- Windows / Linux / macOS

安装依赖：

```bash
pip install -r requirements.txt
```

## 3. 启动方式

```bash
python main.py
```

默认访问地址：

- 前台：`http://127.0.0.1:5000/`
- 管理端：`http://127.0.0.1:5000/frontend/admin.html`

可选环境变量：

- `FLASK_HOST`（默认 `127.0.0.1`）
- `FLASK_PORT`（默认 `5000`）
- `ADMIN_USERNAMES`（默认 `admin`，可配置多个：`admin,alice,bob`）

示例（PowerShell）：

```powershell
$env:FLASK_HOST='0.0.0.0'
$env:FLASK_PORT='5000'
$env:ADMIN_USERNAMES='admin,ops_lead'
python main.py
```

## 4. 管理账号与权限规则（重点）

### 4.1 谁是管理员

后端按以下规则判断管理员（满足任一即可）：

1. 用户 `user_type == 'admin'`
2. 用户名命中环境变量 `ADMIN_USERNAMES`（默认仅 `admin`）

### 4.2 管理账号怎么登录

最简单方式：

1. 前台先注册一个用户名为 `admin` 的账号（默认配置下它就是管理员）
2. 用该账号登录
3. 访问管理端 `http://127.0.0.1:5000/frontend/admin.html`

如果你不想用 `admin` 这个名字：

- 启动前设置 `ADMIN_USERNAMES`，例如 `ops_lead`
- 然后注册/登录 `ops_lead` 即可拥有管理权限

### 4.3 管理端访问保护

管理相关 API 已做权限控制：

- 未登录：`401`
- 已登录但非管理员：`403`

并提供管理员状态接口：

- `GET /api/admin/me`

## 5. 管理端功能说明

### 5.1 数据导入

- `POST /api/admin/import/posts`
- 支持 JSON / CSV 导入帖子

### 5.2 数据看板

- `GET /api/dashboard/hot-rank` 热门榜
- `GET /api/dashboard/trends` 趋势
- `GET /api/dashboard/hot-topics` 热门话题

### 5.3 主题聚类

- `GET /api/analysis/topic-clusters`

### 5.4 推荐

- 个性化推荐：`GET /api/recommend/personalized`
- 相似笔记推荐：`GET /api/recommend/similar`

### 5.5 AI 选题助手

- `GET /api/assistant/topic-ideas`

### 5.6 评论与标签分析

- 评论情感分析：`GET /api/analysis/comment-sentiment`
- 标签匹配审计：`GET /api/analysis/tag-audit`

## 6. 常见问题

### Q1：页面一直“加载中”

通常是前端脚本异常或浏览器缓存旧文件：

1. 重启后端
2. 浏览器强刷（`Ctrl + F5`）
3. 打开开发者工具看 Console 报错

### Q2：管理端提示无权限

检查：

1. 是否已登录
2. 登录账号是否满足管理员规则
3. `ADMIN_USERNAMES` 是否正确设置

### Q3：如何把已有用户改为 `user_type=admin`

可直接更新数据库 `users` 表的 `user_type` 字段为 `admin`。

## 7. 目录结构（核心）

- `backend/`：Flask 路由与应用入口
- `database/`：SQLite 初始化与 DAO
- `frontend/`：前台与管理端页面
- `service/`：推荐服务层
- `recommendation/`：推荐算法模块
- `ml/`：机器学习相关模块
- `mock_data/`：模拟数据生成脚本

