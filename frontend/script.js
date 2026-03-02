(function () {
    const originalFetch = window.fetch.bind(window);
    window.fetch = function (resource, init = {}) {
        init.headers = Object.assign({}, init.headers || {});
        const sid = localStorage.getItem('session_id');
        if (sid && !init.headers.Authorization) {
            init.headers.Authorization = `Bearer ${sid}`;
        }
        if (!init.credentials) init.credentials = 'include';
        return originalFetch(resource, init);
    };
})();

class XiaohongshuApp {
    constructor() {
        this.postsContainer = document.getElementById('postsContainer');
        this.searchInput = document.getElementById('searchInput');
        this.searchIcon = document.getElementById('searchIcon');
        this.loadMoreBtn = document.getElementById('loadMoreBtn');
        this.adminEntry = document.getElementById('adminEntry');

        this.loginBtn = document.getElementById('loginBtn');
        this.registerBtn = document.getElementById('registerBtn');
        this.logoutBtn = document.getElementById('logoutBtn');
        this.usernameDisplay = document.getElementById('usernameDisplay');

        this.loginModal = document.getElementById('loginModal');
        this.registerModal = document.getElementById('registerModal');
        this.postModal = document.getElementById('postModal');

        this.loginForm = document.getElementById('loginForm');
        this.registerForm = document.getElementById('registerForm');

        this.modalImage = document.getElementById('modalImage');
        this.modalTitle = document.getElementById('modalTitle');
        this.modalContent = document.getElementById('modalContent');
        this.modalTags = document.getElementById('modalTags');
        this.modalLikeCount = document.getElementById('modalLikeCount');
        this.modalCollectCount = document.getElementById('modalCollectCount');
        this.modalCommentCount = document.getElementById('modalCommentCount');
        this.modalLikeBtn = document.getElementById('modalLikeBtn');
        this.modalCollectBtn = document.getElementById('modalCollectBtn');

        this.commentsList = document.getElementById('commentsList');
        this.commentInput = document.getElementById('commentInput');
        this.submitCommentBtn = document.getElementById('submitCommentBtn');

        this.currentUser = null;
        this.sessionId = localStorage.getItem('session_id') || null;
        this.currentTag = '';
        this.currentSearch = '';
        this.currentPage = 1;
        this.pageSize = 10;
        this.hasMore = true;
        this.isLoading = false;
        this.currentModalPost = null;

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.checkLoginStatus();
        await this.loadPosts(true);
    }

    bindEvents() {
        document.querySelectorAll('.tag-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                document.querySelectorAll('.tag-btn').forEach((b) => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentTag = btn.dataset.tag || '';
                this.currentSearch = '';
                if (this.searchInput) this.searchInput.value = '';
                await this.loadPosts(true);
            });
        });

        if (this.searchInput) {
            this.searchInput.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter') {
                    this.currentSearch = this.searchInput.value.trim();
                    await this.loadPosts(true);
                }
            });
        }

        if (this.searchIcon) {
            this.searchIcon.addEventListener('click', async () => {
                this.currentSearch = this.searchInput.value.trim();
                await this.loadPosts(true);
            });
        }

        if (this.loadMoreBtn) {
            this.loadMoreBtn.addEventListener('click', async () => {
                if (!this.isLoading && this.hasMore) {
                    this.currentPage += 1;
                    await this.loadPosts(false);
                }
            });
        }

        this.loginBtn?.addEventListener('click', () => this.showModal(this.loginModal));
        this.registerBtn?.addEventListener('click', () => this.showModal(this.registerModal));
        this.logoutBtn?.addEventListener('click', () => this.logout());

        document.querySelectorAll('.close').forEach((el) => {
            el.addEventListener('click', () => {
                const id = el.getAttribute('data-close');
                if (id) this.hideModal(document.getElementById(id));
            });
        });

        [this.loginModal, this.registerModal, this.postModal].forEach((m) => {
            if (!m) return;
            m.addEventListener('click', (e) => {
                if (e.target === m) this.hideModal(m);
            });
        });

        document.getElementById('showRegisterFromLogin')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.hideModal(this.loginModal);
            this.showModal(this.registerModal);
        });

        document.getElementById('showLoginFromRegister')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.hideModal(this.registerModal);
            this.showModal(this.loginModal);
        });

        this.loginForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            const resp = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const result = await resp.json();
            if (!resp.ok || !result.success) {
                alert(result.message || '登录失败');
                return;
            }
            this.sessionId = result.session_id;
            this.currentUser = result.user;
            localStorage.setItem('session_id', result.session_id);
            this.updateAuthUI();
            await this.updateAdminEntry();
            this.hideModal(this.loginModal);
        });

        this.registerForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('registerUsername').value.trim();
            const nickname = document.getElementById('registerNickname').value.trim();
            const password = document.getElementById('registerPassword').value;
            const confirmPassword = document.getElementById('registerConfirmPassword').value;
            if (password !== confirmPassword) {
                alert('两次密码不一致');
                return;
            }
            const resp = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, nickname }),
            });
            const result = await resp.json();
            if (!resp.ok || !result.success) {
                alert(result.message || '注册失败');
                return;
            }
            this.sessionId = result.session_id;
            this.currentUser = result.data?.user || null;
            localStorage.setItem('session_id', result.session_id);
            this.updateAuthUI();
            await this.updateAdminEntry();
            this.hideModal(this.registerModal);
        });

        this.modalLikeBtn?.addEventListener('click', async () => {
            if (!this.currentModalPost) return;
            if (!this.currentUser) return alert('请先登录');
            const r = await fetch(`/api/posts/${this.currentModalPost.post_id}/like`, { method: 'POST' });
            const j = await r.json();
            if (j.success) {
                this.currentModalPost.likes = j.like_count;
                this.modalLikeCount.textContent = j.like_count;
                await this.loadPosts(true);
            }
        });

        this.modalCollectBtn?.addEventListener('click', async () => {
            if (!this.currentModalPost) return;
            if (!this.currentUser) return alert('请先登录');
            const r = await fetch(`/api/posts/${this.currentModalPost.post_id}/collect`, { method: 'POST' });
            const j = await r.json();
            if (j.success) {
                this.currentModalPost.collects = j.collects;
                this.modalCollectCount.textContent = j.collects;
                await this.loadPosts(true);
            }
        });

        this.submitCommentBtn?.addEventListener('click', async () => {
            if (!this.currentModalPost) return;
            if (!this.currentUser) return alert('请先登录');
            const content = this.commentInput.value.trim();
            if (!content) return;
            const r = await fetch('/api/comments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ post_id: this.currentModalPost.post_id, content }),
            });
            const j = await r.json();
            if (!j.success) return alert(j.message || '评论失败');
            this.commentInput.value = '';
            await this.openPostModal(this.currentModalPost);
        });
    }

    async checkLoginStatus() {
        if (!this.sessionId) {
            this.updateAuthUI();
            await this.updateAdminEntry();
            return;
        }
        try {
            const resp = await fetch('/api/current_user', {
                headers: { Authorization: `Bearer ${this.sessionId}` },
            });
            const result = await resp.json();
            if (resp.ok && result.success) {
                this.currentUser = result.user;
            } else {
                localStorage.removeItem('session_id');
                this.sessionId = null;
                this.currentUser = null;
            }
        } catch (_) {
            localStorage.removeItem('session_id');
            this.sessionId = null;
            this.currentUser = null;
        }
        this.updateAuthUI();
        await this.updateAdminEntry();
    }

    async updateAdminEntry() {
        if (!this.adminEntry) return;
        this.adminEntry.classList.add('hidden');
        if (!this.sessionId) return;
        try {
            const resp = await fetch('/api/admin/me', {
                headers: { Authorization: `Bearer ${this.sessionId}` },
            });
            const result = await resp.json();
            if (resp.ok && result.success && result.is_admin) {
                this.adminEntry.classList.remove('hidden');
            }
        } catch (_) {}
    }

    updateAuthUI() {
        if (this.currentUser) {
            this.usernameDisplay.textContent = this.currentUser.nickname || this.currentUser.username;
            this.usernameDisplay.classList.remove('hidden');
            this.loginBtn.classList.add('hidden');
            this.registerBtn.classList.add('hidden');
            this.logoutBtn.classList.remove('hidden');
        } else {
            this.usernameDisplay.classList.add('hidden');
            this.loginBtn.classList.remove('hidden');
            this.registerBtn.classList.remove('hidden');
            this.logoutBtn.classList.add('hidden');
        }
    }

    async logout() {
        if (this.sessionId) {
            await fetch('/api/logout', { method: 'POST' }).catch(() => null);
        }
        this.sessionId = null;
        this.currentUser = null;
        localStorage.removeItem('session_id');
        this.updateAuthUI();
        await this.updateAdminEntry();
    }

    async loadPosts(reset = false) {
        if (this.isLoading) return;
        this.isLoading = true;

        if (reset) {
            this.currentPage = 1;
            this.hasMore = true;
            this.postsContainer.innerHTML = '<div class="loading">加载中...</div>';
        }

        const params = new URLSearchParams({
            page: String(this.currentPage),
            limit: String(this.pageSize),
        });
        if (this.currentTag) params.set('tag', this.currentTag);
        if (this.currentSearch) params.set('q', this.currentSearch);

        try {
            const resp = await fetch(`/api/posts?${params.toString()}`);
            const result = await resp.json();
            if (!resp.ok || !result.success) {
                throw new Error(result.message || '加载失败');
            }
            const rows = result.data || [];
            this.hasMore = !!result.has_more;

            if (reset) this.postsContainer.innerHTML = '';
            if (!rows.length && reset) {
                this.postsContainer.innerHTML = '<div class="loading">暂无内容</div>';
            } else {
                rows.forEach((post) => this.postsContainer.appendChild(this.createPostCard(post)));
            }
        } catch (error) {
            this.postsContainer.innerHTML = `<div class="error">${error.message}</div>`;
        } finally {
            this.isLoading = false;
            this.loadMoreBtn.style.display = this.hasMore ? 'inline-block' : 'none';
        }
    }

    createPostCard(post) {
        const card = document.createElement('article');
        card.className = 'post-card';
        card.dataset.postId = post.post_id;

        const firstImage = (post.images && post.images[0]) || 'https://via.placeholder.com/600x400?text=No+Image';
        const tags = (post.tags || []).slice(0, 3).map((t) => `#${t}`).join(' ');

        card.innerHTML = `
            <div class="post-images image-single">
                <img class="post-image" src="${firstImage}" alt="${this.escapeHTML(post.title)}">
            </div>
            <div class="post-content">
                <h3 class="post-title">${this.escapeHTML(post.title)}</h3>
                <p class="post-text">${this.escapeHTML(post.content || '')}</p>
                <div class="post-tags">${this.escapeHTML(tags)}</div>
                <div class="post-meta"><span class="post-time">${this.escapeHTML(post.publish_time || '')}</span></div>
                <div class="post-stats">
                    <span class="interact-btn"><i class="fas fa-heart"></i> ${post.likes || 0}</span>
                    <span class="interact-btn"><i class="fas fa-bookmark"></i> ${post.collects || 0}</span>
                    <span class="interact-btn"><i class="fas fa-comment"></i> ${post.comments || 0}</span>
                </div>
            </div>
        `;

        card.addEventListener('click', () => this.openPostModal(post));
        return card;
    }

    async openPostModal(post) {
        this.currentModalPost = post;
        this.modalImage.src = (post.images && post.images[0]) || 'https://via.placeholder.com/600x400?text=No+Image';
        this.modalTitle.textContent = post.title || '';
        this.modalContent.textContent = post.content || '';
        this.modalLikeCount.textContent = post.likes || 0;
        this.modalCollectCount.textContent = post.collects || 0;
        this.modalCommentCount.textContent = post.comments || 0;
        this.modalTags.innerHTML = (post.tags || []).map((t) => `<span>#${this.escapeHTML(t)}</span>`).join('');

        try {
            const resp = await fetch(`/api/comments?post_id=${post.post_id}`);
            const result = await resp.json();
            const comments = result.success ? (result.data || []) : [];
            this.commentsList.innerHTML = comments.length
                ? comments.map((c) => `<div class="comment-item"><img src="${c.avatar}" class="user-avatar"><div class="comment-content"><div class="comment-header"><span class="comment-username">${this.escapeHTML(c.nickname || c.username || '用户')}</span><span class="comment-time">${this.escapeHTML(c.publish_time || '')}</span></div><div class="comment-text">${this.escapeHTML(c.content || '')}</div></div></div>`).join('')
                : '<p>暂无评论</p>';
        } catch (_) {
            this.commentsList.innerHTML = '<p>评论加载失败</p>';
        }

        this.showModal(this.postModal);
    }

    showModal(modal) {
        if (!modal) return;
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    hideModal(modal) {
        if (!modal) return;
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    escapeHTML(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.__app = new XiaohongshuApp();
});
