function toTable(rows, columns) {
    if (!rows || rows.length === 0) return "<p>暂无数据</p>";
    const header = columns.map((c) => `<th>${c.label}</th>`).join("");
    const body = rows
        .map((row) => `<tr>${columns.map((c) => `<td>${c.render ? c.render(row) : (row[c.key] ?? "")}</td>`).join("")}</tr>`)
        .join("");
    return `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
}

async function apiGet(url) {
    const resp = await fetch(url);
    const data = await resp.json();
    if (!resp.ok) {
        throw new Error(data.message || `请求失败: ${resp.status}`);
    }
    return data;
}

async function ensureAdmin() {
    try {
        const result = await apiGet("/api/admin/me");
        if (!result.is_admin) {
            throw new Error("当前账号不是管理员");
        }
        return true;
    } catch (err) {
        document.body.innerHTML = `
            <div style="max-width:720px;margin:80px auto;padding:24px;background:#fff;border-radius:12px;box-shadow:0 8px 24px rgba(15,23,42,.1);font-family:'Segoe UI','PingFang SC',sans-serif;">
                <h2 style="margin-top:0;">管理端权限校验失败</h2>
                <p>${err.message}</p>
                <p>请先使用管理员账号登录前台，再进入管理端。</p>
                <a href="/" style="color:#2563eb;">返回前台登录</a>
            </div>
        `;
        return false;
    }
}

async function refreshDashboard() {
    const [hotRank, trend, topics] = await Promise.all([
        apiGet("/api/dashboard/hot-rank?limit=10"),
        apiGet("/api/dashboard/trends?days=14"),
        apiGet("/api/dashboard/hot-topics?limit=10"),
    ]);

    document.getElementById("hotRank").innerHTML = toTable(hotRank.data || [], [
        { key: "rank", label: "#" },
        { key: "title", label: "标题" },
        { key: "hot_score", label: "热度" },
    ]);

    document.getElementById("trendBoard").innerHTML = toTable(trend.data || [], [
        { key: "day", label: "日期" },
        { key: "post_count", label: "发帖数" },
        { key: "avg_engagement", label: "平均互动" },
    ]);

    document.getElementById("hotTopics").innerHTML = toTable(topics.data || [], [
        { key: "tag", label: "话题" },
        { key: "post_count", label: "帖子数" },
        { key: "topic_engagement", label: "互动值" },
    ]);
}

async function runClusters() {
    const result = await apiGet("/api/analysis/topic-clusters?limit=300");
    const data = result.data || [];
    if (!data.length) {
        document.getElementById("clusterResult").innerHTML = "<p>暂无聚类结果</p>";
        return;
    }
    document.getElementById("clusterResult").innerHTML = data
        .map(
            (c) =>
                `<div><b>${c.label}</b>（${c.size}）<br>关键词: ${c.keywords.join(", ")}<br>样例: ${
                    (c.sample_posts || []).map((p) => `${p.post_id}:${p.title}`).join(" | ")
                }</div>`
        )
        .join("<hr>");
}

async function loadPersonalized() {
    const userId = document.getElementById("userIdInput").value;
    if (!userId) return;
    const result = await apiGet(`/api/recommend/personalized?user_id=${encodeURIComponent(userId)}&limit=10`);
    document.getElementById("personalizedResult").innerHTML = toTable(result.data || [], [
        { key: "post_id", label: "ID" },
        { key: "title", label: "标题" },
        { key: "hot_score", label: "热度" },
    ]);
}

async function loadSimilar() {
    const postId = document.getElementById("postIdInput").value;
    if (!postId) return;
    const result = await apiGet(`/api/recommend/similar?post_id=${encodeURIComponent(postId)}&limit=10`);
    document.getElementById("similarResult").innerHTML = toTable(result.data || [], [
        { key: "post_id", label: "ID" },
        { key: "title", label: "标题" },
        { key: "similarity_score", label: "相似度" },
    ]);
}

async function runAssistant() {
    const result = await apiGet("/api/assistant/topic-ideas?count=6");
    const rows = result.data || [];
    document.getElementById("assistantResult").innerHTML = rows.length
        ? `<ul>${rows
              .map(
                  (r) =>
                      `<li><b>${r.direction}</b> | ${r.title_suggestion}<br>${r.publish_time_suggestion}<br>${r.reasoning}</li>`
              )
              .join("")}</ul>`
        : "<p>暂无建议</p>";
}

async function runSentiment() {
    const postId = document.getElementById("sentimentPostId").value;
    const url = postId
        ? `/api/analysis/comment-sentiment?post_id=${encodeURIComponent(postId)}&limit=200`
        : "/api/analysis/comment-sentiment?limit=200";
    const result = await apiGet(url);
    const s = result.summary || {};
    document.getElementById("sentimentResult").innerHTML = `
        <p>总量: ${result.total || 0}</p>
        <p>正向: ${s.positive || 0} | 中性: ${s.neutral || 0} | 负向: ${s.negative || 0}</p>
        ${toTable((result.data || []).slice(0, 20), [
            { key: "post_id", label: "帖子ID" },
            { key: "sentiment", label: "情感" },
            { key: "content", label: "评论" },
        ])}
    `;
}

async function runTagAudit() {
    const result = await apiGet("/api/analysis/tag-audit?limit=100");
    document.getElementById("tagAuditResult").innerHTML = toTable(result.data || [], [
        { key: "post_id", label: "帖子ID" },
        { key: "title", label: "标题" },
        { key: "match_score", label: "匹配分" },
        { key: "suggestion", label: "建议" },
    ]);
}

async function importData() {
    const file = document.getElementById("importFile").files[0];
    const text = document.getElementById("importJson").value.trim();
    const output = document.getElementById("importResult");

    try {
        let result;
        if (file) {
            const form = new FormData();
            form.append("file", file);
            const resp = await fetch("/api/admin/import/posts", { method: "POST", body: form });
            result = await resp.json();
        } else if (text) {
            const payload = JSON.parse(text);
            const resp = await fetch("/api/admin/import/posts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            result = await resp.json();
        } else {
            output.textContent = "请先选择文件或粘贴 JSON";
            return;
        }
        output.textContent = JSON.stringify(result, null, 2);
    } catch (err) {
        output.textContent = `导入失败: ${err.message}`;
    }
}

function bindEvents() {
    document.getElementById("importBtn").addEventListener("click", importData);
    document.getElementById("refreshDashboardBtn").addEventListener("click", refreshDashboard);
    document.getElementById("runClusterBtn").addEventListener("click", runClusters);
    document.getElementById("loadPersonalizedBtn").addEventListener("click", loadPersonalized);
    document.getElementById("loadSimilarBtn").addEventListener("click", loadSimilar);
    document.getElementById("runAssistantBtn").addEventListener("click", runAssistant);
    document.getElementById("runSentimentBtn").addEventListener("click", runSentiment);
    document.getElementById("runTagAuditBtn").addEventListener("click", runTagAudit);
}

(async function init() {
    const ok = await ensureAdmin();
    if (!ok) return;
    bindEvents();
    await refreshDashboard();
})();
