/* ═══════════════════════════════════════════════════════════════
   GymVault - Frontend Application
   Single Page Application with async/await throughout
   ═══════════════════════════════════════════════════════════════ */

// ─── API Base URL ────────────────────────────────────────────
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || !window.location.hostname
    ? 'http://localhost:5000/api'
    : '/api';

// ─── State Management ────────────────────────────────────────
const state = {
    currentPage: 'dashboard',
    members: [],
    plans: [],
    payments: [],
    searchQuery: '',
    filterStatus: 'all',
    healthData: null,
    checkinTimeout: null
};

// ─── Avatar Colors ───────────────────────────────────────────
const avatarColors = [
    '#1e3a8a', '#2563eb', '#4f46e5', '#7c3aed',
    '#059669', '#0891b2', '#d97706', '#dc2626',
    '#6366f1', '#8b5cf6', '#0d9488', '#ea580c'
];

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

function navigateTo(page) {
    state.currentPage = page;

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Load page content
    const main = document.getElementById('main-content');
    main.innerHTML = '';

    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'members': loadMembers(); break;
        case 'plans': loadPlans(); break;
        case 'payments': loadPayments(); break;
        case 'checkin': loadCheckins(); break;
        case 'aws': loadAWSPanel(); break;
        case 'settings': loadSettings(); break;
        default: loadDashboard();
    }
}

// ═══════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const d = new Date(dateString);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch { return dateString; }
}

function formatTime(dateString) {
    if (!dateString) return '';
    try {
        const d = new Date(dateString);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch { return ''; }
}

function formatCurrency(amount) {
    return '$' + Number(amount || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function getStatusColor(status) {
    switch (status) {
        case 'Active': return 'active';
        case 'Expiring Soon': return 'expiring';
        case 'Expired': return 'expired';
        default: return 'active';
    }
}

function getStatusBadge(status) {
    const cls = getStatusColor(status);
    return `<span class="badge badge-${cls}">${status}</span>`;
}

function getPaymentStatusBadge(status) {
    const cls = status === 'Paid' ? 'paid' : status === 'Pending' ? 'pending' : 'failed';
    return `<span class="badge badge-${cls}">${status}</span>`;
}

function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return parts[0][0].toUpperCase();
}

function getAvatarColor(name) {
    if (!name) return avatarColors[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return avatarColors[Math.abs(hash) % avatarColors.length];
}

function daysRemaining(endDate) {
    if (!endDate) return 0;
    const end = new Date(endDate);
    const now = new Date();
    return Math.ceil((end - now) / (1000 * 60 * 60 * 24));
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = `
            <div class="skeleton skeleton-card" style="height:120px;margin-bottom:16px"></div>
            <div class="skeleton skeleton-card" style="height:120px;margin-bottom:16px"></div>
            <div class="skeleton skeleton-card" style="height:80px"></div>
        `;
    }
}

function showSkeletonCards(elementId, count = 4) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = Array(count).fill('').map(() =>
            '<div class="skeleton skeleton-card" style="height:200px"></div>'
        ).join('');
    }
}

// ═══════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
        <button class="toast-close" onclick="this.parentElement.classList.add('removing'); setTimeout(() => this.parentElement.remove(), 300)">
            <i class="fas fa-times"></i>
        </button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }
    }, 3500);
}

// ═══════════════════════════════════════════════════════════════
// MODAL MANAGEMENT
// ═══════════════════════════════════════════════════════════════

function openModal(content, size = '') {
    const overlay = document.getElementById('modal-overlay');
    const container = document.getElementById('modal-container');
    container.className = `modal ${size}`;
    container.innerHTML = content;
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

function handleOverlayClick(event) {
    if (event.target.id === 'modal-overlay') closeModal();
}

// ═══════════════════════════════════════════════════════════════
// CONFIRMATION DIALOG
// ═══════════════════════════════════════════════════════════════

function showConfirm(title, message, onConfirm, type = 'danger') {
    const content = `
        <div class="modal-header">
            <h3>Confirm Action</h3>
            <button class="modal-close" onclick="closeModal()"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="confirm-dialog">
                <div class="confirm-icon ${type}">
                    <i class="fas ${type === 'danger' ? 'fa-trash-alt' : 'fa-exclamation-triangle'}"></i>
                </div>
                <h3>${title}</h3>
                <p>${message}</p>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-${type}" id="confirm-btn" onclick="document.__confirmAction()">
                ${type === 'danger' ? 'Delete' : 'Confirm'}
            </button>
        </div>
    `;
    document.__confirmAction = async () => {
        const btn = document.getElementById('confirm-btn');
        btn.innerHTML = '<div class="spinner"></div> Processing...';
        btn.disabled = true;
        try {
            await onConfirm();
        } catch (e) {
            showToast('Action failed: ' + e.message, 'error');
        }
        closeModal();
    };
    openModal(content);
}

// ═══════════════════════════════════════════════════════════════
// API HELPERS
// ═══════════════════════════════════════════════════════════════

async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`);
        const data = await res.json();
        return data;
    } catch (error) {
        console.error(`GET ${endpoint} failed:`, error);
        return { success: false, error: error.message };
    }
}

async function apiPost(endpoint, body) {
    try {
        const res = await fetch(`${API}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        return data;
    } catch (error) {
        console.error(`POST ${endpoint} failed:`, error);
        return { success: false, error: error.message };
    }
}

async function apiPut(endpoint, body) {
    try {
        const res = await fetch(`${API}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        return data;
    } catch (error) {
        console.error(`PUT ${endpoint} failed:`, error);
        return { success: false, error: error.message };
    }
}

async function apiDelete(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`, { method: 'DELETE' });
        const data = await res.json();
        return data;
    } catch (error) {
        console.error(`DELETE ${endpoint} failed:`, error);
        return { success: false, error: error.message };
    }
}

async function apiPostForm(endpoint, formData) {
    try {
        const res = await fetch(`${API}${endpoint}`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        return data;
    } catch (error) {
        console.error(`POST (form) ${endpoint} failed:`, error);
        return { success: false, error: error.message };
    }
}

// ═══════════════════════════════════════════════════════════════
// HEALTH CHECK
// ═══════════════════════════════════════════════════════════════

async function checkHealth() {
    try {
        const result = await apiGet('/health');
        if (result.success) {
            state.healthData = result.data;
            updateStatusDots(result.data.services);
        }
    } catch (error) {
        console.warn('Health check failed:', error);
    }
}

function updateStatusDots(services) {
    if (!services) return;
    const setDot = (id, healthy) => {
        const dot = document.getElementById(id);
        if (dot) {
            dot.className = `status-dot ${healthy ? 'green' : 'red'}`;
        }
    };
    setDot('dot-mongo', services.mongodb?.healthy);
    setDot('dot-s3', services.s3?.healthy);
    setDot('dot-kms', services.kms?.healthy);
    setDot('dot-sns', services.sns?.healthy);
}

// ═══════════════════════════════════════════════════════════════
// PAGE 1: DASHBOARD
// ═══════════════════════════════════════════════════════════════

async function loadDashboard() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header">
                <h2>Dashboard</h2>
                <p>Overview of your gym operations</p>
            </div>
            <div id="dashboard-stats-1" class="stats-grid">
                ${Array(4).fill('<div class="skeleton skeleton-card" style="height:130px"></div>').join('')}
            </div>
            <div id="dashboard-stats-2" class="stats-grid stats-grid-3">
                ${Array(3).fill('<div class="skeleton skeleton-card" style="height:130px"></div>').join('')}
            </div>
            <div id="dashboard-aws-strip"></div>
            <div class="dashboard-grid-2" id="dashboard-bottom">
                <div class="skeleton skeleton-card" style="height:300px"></div>
                <div class="skeleton skeleton-card" style="height:300px"></div>
            </div>
        </div>
    `;

    try {
        const [statsResult, healthResult, checkinsResult, membersResult] = await Promise.all([
            apiGet('/dashboard/stats'),
            apiGet('/health'),
            apiGet('/checkins/today'),
            apiGet('/members?status=Expiring Soon')
        ]);

        // Stats Row 1
        if (statsResult.success) {
            const s = statsResult.data;
            document.getElementById('dashboard-stats-1').innerHTML = `
                <div class="stat-card indigo">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Total Members</span>
                        <div class="stat-card-icon indigo"><i class="fas fa-users"></i></div>
                    </div>
                    <div class="stat-card-value">${s.total_members || 0}</div>
                    <div class="stat-card-sub">All registered members</div>
                </div>
                <div class="stat-card green">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Active Members</span>
                        <div class="stat-card-icon green"><i class="fas fa-user-check"></i></div>
                    </div>
                    <div class="stat-card-value">${s.active_members || 0}</div>
                    <div class="stat-card-sub">Currently active</div>
                </div>
                <div class="stat-card amber clickable" onclick="navigateTo('members')">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Expiring Soon</span>
                        <div class="stat-card-icon amber"><i class="fas fa-exclamation-triangle"></i></div>
                    </div>
                    <div class="stat-card-value">${s.expiring_soon || 0}</div>
                    <div class="stat-card-sub">Within 7 days</div>
                </div>
                <div class="stat-card cyan">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Today's Check-ins</span>
                        <div class="stat-card-icon cyan"><i class="fas fa-calendar-check"></i></div>
                    </div>
                    <div class="stat-card-value">${s.todays_checkins || 0}</div>
                    <div class="stat-card-sub">Checked in today</div>
                </div>
            `;

            // Stats Row 2
            document.getElementById('dashboard-stats-2').innerHTML = `
                <div class="stat-card blue">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Total Revenue</span>
                        <div class="stat-card-icon blue"><i class="fas fa-dollar-sign"></i></div>
                    </div>
                    <div class="stat-card-value">${formatCurrency(s.total_revenue)}</div>
                    <div class="stat-card-sub">Lifetime earnings</div>
                </div>
                <div class="stat-card purple">
                    <div class="stat-card-header">
                        <span class="stat-card-label">This Month Revenue</span>
                        <div class="stat-card-icon purple"><i class="fas fa-chart-line"></i></div>
                    </div>
                    <div class="stat-card-value">${formatCurrency(s.revenue_this_month)}</div>
                    <div class="stat-card-sub">Current month</div>
                </div>
                <div class="stat-card rose">
                    <div class="stat-card-header">
                        <span class="stat-card-label">New Members</span>
                        <div class="stat-card-icon rose"><i class="fas fa-user-plus"></i></div>
                    </div>
                    <div class="stat-card-value">${s.new_members_this_month || 0}</div>
                    <div class="stat-card-sub">This month</div>
                </div>
            `;
        }

        // AWS Status Strip
        if (healthResult.success) {
            const svc = healthResult.data.services;
            state.healthData = healthResult.data;
            updateStatusDots(svc);

            document.getElementById('dashboard-aws-strip').innerHTML = `
                <div class="aws-status-strip">
                    <span class="strip-label"><i class="fas fa-cloud"></i> AWS Services</span>
                    <div class="aws-status-items">
                        <div class="aws-status-item">
                            <div class="status-dot ${svc.mongodb?.healthy ? 'green' : 'red'}"></div> MongoDB
                        </div>
                        <div class="aws-status-item">
                            <div class="status-dot ${svc.s3?.healthy ? 'green' : 'red'}"></div> S3
                        </div>
                        <div class="aws-status-item">
                            <div class="status-dot ${svc.kms?.healthy ? 'green' : 'red'}"></div> KMS
                        </div>
                        <div class="aws-status-item">
                            <div class="status-dot ${svc.sns?.healthy ? 'green' : 'red'}"></div> SNS
                        </div>
                        <div class="aws-status-item">
                            <div class="status-dot ${svc.secrets_manager?.healthy ? 'green' : 'red'}"></div> Secrets
                        </div>
                    </div>
                </div>
            `;
        }

        // Bottom Grid: Recent Check-ins + Expiring Soon
        const checkinsHtml = (checkinsResult.success && checkinsResult.data?.length)
            ? checkinsResult.data.slice(0, 8).map(c => `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <span class="timeline-name">${c.member_name}</span>
                    <span class="timeline-time">${formatTime(c.checkin_time)}</span>
                </div>
            `).join('')
            : '<div class="empty-state"><div class="empty-state-icon">✅</div><h3>No check-ins today yet</h3><p>Members will appear here after checking in</p></div>';

        const expiringHtml = (membersResult.success && membersResult.data?.length)
            ? membersResult.data.slice(0, 5).map(m => {
                const days = daysRemaining(m.membership_end);
                return `
                    <div class="timeline-item">
                        <div class="status-dot yellow"></div>
                        <div style="flex:1">
                            <span class="timeline-name">${m.full_name}</span>
                            <div style="font-size:12px;color:var(--text-muted)">${m.plan_name} · ${days} days left</div>
                        </div>
                    </div>
                `;
            }).join('') + `
                <div style="padding:12px 0">
                    <button class="btn btn-warning btn-sm" onclick="sendExpiryAlerts()">
                        <i class="fas fa-bell"></i> Send Alerts
                    </button>
                </div>
            `
            : '<div class="empty-state"><div class="empty-state-icon">🎉</div><h3>No expiring memberships</h3><p>All members are in good standing</p></div>';

        document.getElementById('dashboard-bottom').innerHTML = `
            <div class="card">
                <div class="card-header"><h3><i class="fas fa-clock" style="color:var(--primary);margin-right:8px"></i> Recent Check-ins</h3></div>
                <div class="card-body">${checkinsHtml}</div>
            </div>
            <div class="card">
                <div class="card-header"><h3><i class="fas fa-exclamation-triangle" style="color:var(--warning);margin-right:8px"></i> Expiring Soon</h3></div>
                <div class="card-body">${expiringHtml}</div>
            </div>
        `;

    } catch (error) {
        showToast('Failed to load dashboard data', 'error');
        console.error('Dashboard error:', error);
    }
}

async function sendExpiryAlerts() {
    showConfirm(
        'Send Expiry Alerts',
        'This will send email alerts to all members with expiring memberships. Continue?',
        async () => {
            const result = await apiPost('/aws/send-expiry-alerts', {});
            if (result.success) {
                showToast(`${result.data?.alerts_sent || 0} expiry alert(s) sent`, 'success');
            } else {
                showToast('Failed to send alerts: ' + (result.error || 'Unknown error'), 'error');
            }
        },
        'warning'
    );
}

// ═══════════════════════════════════════════════════════════════
// PAGE 2: MEMBERS
// ═══════════════════════════════════════════════════════════════

async function loadMembers(filter, search) {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header">
                <h2>Members</h2>
                <p>Manage gym memberships</p>
            </div>
            <div class="toolbar">
                <div class="toolbar-left">
                    <div class="toolbar-search">
                        <i class="fas fa-search"></i>
                        <input type="text" id="member-search" placeholder="Search by name, email, or ID..."
                               value="${search || state.searchQuery}" oninput="debounceSearch(this.value)">
                    </div>
                    <div class="toolbar-filter">
                        <select id="member-filter" onchange="filterMembers(this.value)">
                            <option value="all" ${state.filterStatus === 'all' ? 'selected' : ''}>All Members</option>
                            <option value="Active" ${state.filterStatus === 'Active' ? 'selected' : ''}>Active</option>
                            <option value="Expiring Soon" ${state.filterStatus === 'Expiring Soon' ? 'selected' : ''}>Expiring Soon</option>
                            <option value="Expired" ${state.filterStatus === 'Expired' ? 'selected' : ''}>Expired</option>
                        </select>
                    </div>
                </div>
                <button class="btn btn-primary" onclick="openAddMemberModal()">
                    <i class="fas fa-user-plus"></i> Add Member
                </button>
            </div>
            <div class="members-grid" id="members-grid">
                ${Array(6).fill('<div class="skeleton skeleton-card" style="height:280px"></div>').join('')}
            </div>
        </div>
    `;

    try {
        let endpoint = '/members?';
        const statusFilter = filter || state.filterStatus;
        const searchQuery = search !== undefined ? search : state.searchQuery;

        if (statusFilter && statusFilter !== 'all') endpoint += `status=${encodeURIComponent(statusFilter)}&`;
        if (searchQuery) endpoint += `search=${encodeURIComponent(searchQuery)}&`;

        const result = await apiGet(endpoint);

        if (result.success) {
            state.members = result.data || [];
            renderMembersGrid();
        } else {
            document.getElementById('members-grid').innerHTML = `
                <div class="empty-state" style="grid-column:1/-1">
                    <div class="empty-state-icon">⚠️</div>
                    <h3>Error loading members</h3>
                    <p>${result.error || 'Please try again'}</p>
                </div>
            `;
        }
    } catch (error) {
        showToast('Failed to load members', 'error');
    }
}

function renderMembersGrid() {
    const grid = document.getElementById('members-grid');
    if (!grid) return;

    if (!state.members.length) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1">
                <div class="empty-state-icon">👥</div>
                <h3>No members yet</h3>
                <p>Add your first member to get started!</p>
                <button class="btn btn-primary mt-2" onclick="openAddMemberModal()">
                    <i class="fas fa-user-plus"></i> Add Member
                </button>
            </div>
        `;
        return;
    }

    grid.innerHTML = state.members.map(m => renderMemberCard(m)).join('');
}

function renderMemberCard(member) {
    const avatar = member.photo_url
        ? `<img src="${member.photo_url}" alt="${member.full_name}" class="member-avatar" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        : '';

    const placeholder = `<div class="member-avatar-placeholder" style="background:${getAvatarColor(member.full_name)};${member.photo_url ? 'display:none' : ''}">${getInitials(member.full_name)}</div>`;

    const days = daysRemaining(member.membership_end);

    return `
        <div class="member-card">
            <div class="member-card-top">
                ${avatar}${placeholder}
                <div class="member-card-info">
                    <h4>${member.full_name}</h4>
                    <div class="member-card-badges">
                        <span class="badge badge-id">${member.member_id}</span>
                        <span class="badge badge-plan">${member.plan_name}</span>
                        ${getStatusBadge(member.status)}
                    </div>
                </div>
            </div>
            <div class="member-card-details">
                <div class="member-card-detail">
                    <i class="fas fa-calendar"></i>
                    <span>Expires: ${formatDate(member.membership_end)} ${days > 0 ? `(${days}d)` : ''}</span>
                </div>
                <div class="member-card-detail">
                    <i class="fas fa-phone"></i>
                    <span>${member.phone || 'N/A'}</span>
                </div>
            </div>
            <div class="member-card-actions">
                <button class="btn btn-secondary btn-sm" onclick="viewMemberDetail('${member.member_id}')">
                    <i class="fas fa-eye"></i> View
                </button>
                <button class="btn btn-success btn-sm" onclick="openRenewModal('${member.member_id}')">
                    <i class="fas fa-sync-alt"></i> Renew
                </button>
                <button class="btn btn-danger btn-sm" onclick="deleteMember('${member.member_id}', '${member.full_name}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `;
}

let searchDebounce = null;
function debounceSearch(value) {
    state.searchQuery = value;
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => loadMembers(state.filterStatus, value), 350);
}

function filterMembers(value) {
    state.filterStatus = value;
    loadMembers(value, state.searchQuery);
}

// ─── Add Member Modal ────────────────────────────────────────
async function openAddMemberModal() {
    // Load plans first
    const plansResult = await apiGet('/plans');
    const plans = plansResult.success ? plansResult.data : [];

    const planOptions = plans.map(p =>
        `<option value="${p._id}">${p.plan_name} - ${formatCurrency(p.price)} / ${p.duration_months}mo</option>`
    ).join('');

    const content = `
        <div class="modal-header">
            <h3><i class="fas fa-user-plus" style="color:var(--primary);margin-right:8px"></i> Add New Member</h3>
            <button class="modal-close" onclick="closeModal()"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <form id="add-member-form" onsubmit="submitAddMember(event)">
                <div class="form-group">
                    <label>Profile Photo</label>
                    <div class="photo-upload-area" onclick="document.getElementById('photo-input').click()">
                        <div id="photo-preview-container">
                            <i class="fas fa-cloud-upload-alt"></i>
                            <p>Click to upload photo</p>
                            <span class="hint">PNG, JPG, GIF up to 5MB</span>
                        </div>
                    </div>
                    <input type="file" id="photo-input" accept="image/*" style="display:none" onchange="previewPhoto(this)">
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>Full Name <span class="required">*</span></label>
                        <input type="text" class="form-control" id="add-name" required placeholder="John Doe">
                    </div>
                    <div class="form-group">
                        <label>Email <span class="required">*</span></label>
                        <input type="email" class="form-control" id="add-email" required placeholder="john@example.com">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>Phone <span class="required">*</span></label>
                        <input type="text" class="form-control" id="add-phone" required placeholder="+1 234 567 8900">
                    </div>
                    <div class="form-group">
                        <label>Age</label>
                        <input type="number" class="form-control" id="add-age" min="10" max="100" placeholder="25">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>Gender</label>
                        <select class="form-control" id="add-gender">
                            <option value="Male">Male</option>
                            <option value="Female">Female</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Select Plan <span class="required">*</span></label>
                        <select class="form-control" id="add-plan" required>
                            <option value="">Choose a plan...</option>
                            ${planOptions}
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <label>Address</label>
                    <textarea class="form-control" id="add-address" rows="2" placeholder="123 Main St, City"></textarea>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" id="add-member-btn" onclick="submitAddMember(event)">
                <i class="fas fa-user-plus"></i> Add Member + Send Welcome
            </button>
        </div>
    `;

    openModal(content, 'modal-lg');
}

function previewPhoto(input) {
    const file = input.files[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
        showToast('Photo must be under 5MB', 'warning');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('photo-preview-container').innerHTML = `
            <img src="${e.target.result}" class="photo-preview" alt="Preview">
            <p style="color:var(--text-muted);font-size:12px">${file.name}</p>
        `;
    };
    reader.readAsDataURL(file);
}

async function submitAddMember(event) {
    if (event) event.preventDefault();

    const btn = document.getElementById('add-member-btn');
    btn.innerHTML = '<div class="spinner"></div> Adding...';
    btn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('full_name', document.getElementById('add-name').value);
        formData.append('email', document.getElementById('add-email').value);
        formData.append('phone', document.getElementById('add-phone').value);
        formData.append('age', document.getElementById('add-age').value || 0);
        formData.append('gender', document.getElementById('add-gender').value);
        formData.append('address', document.getElementById('add-address').value);
        formData.append('plan_id', document.getElementById('add-plan').value);

        const photoInput = document.getElementById('photo-input');
        if (photoInput.files[0]) {
            formData.append('photo', photoInput.files[0]);
        }

        const result = await apiPostForm('/members', formData);

        if (result.success) {
            showToast(`Member ${result.data?.member_id} added successfully! 🎉`, 'success');
            closeModal();
            loadMembers();
        } else {
            showToast(result.error || 'Failed to add member', 'error');
            btn.innerHTML = '<i class="fas fa-user-plus"></i> Add Member + Send Welcome';
            btn.disabled = false;
        }
    } catch (error) {
        showToast('Error adding member: ' + error.message, 'error');
        btn.innerHTML = '<i class="fas fa-user-plus"></i> Add Member + Send Welcome';
        btn.disabled = false;
    }
}

// ─── View Member Detail ──────────────────────────────────────
async function viewMemberDetail(memberId) {
    const result = await apiGet(`/members/${memberId}`);
    if (!result.success) {
        showToast('Failed to load member details', 'error');
        return;
    }

    const m = result.data;
    const avatarHtml = m.photo_url
        ? `<img src="${m.photo_url}" alt="${m.full_name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        : '';
    const placeholderHtml = `<div class="avatar-placeholder-lg" style="background:${getAvatarColor(m.full_name)};${m.photo_url ? 'display:none' : ''}">${getInitials(m.full_name)}</div>`;

    const content = `
        <div class="modal-header">
            <h3><span class="badge badge-id">${m.member_id}</span> ${m.full_name}</h3>
            <button class="modal-close" onclick="closeModal()"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="member-detail-layout">
                <div class="member-detail-photo">
                    ${avatarHtml}${placeholderHtml}
                    ${getStatusBadge(m.status)}
                </div>
                <div>
                    <div class="member-detail-tabs">
                        <div class="member-detail-tab active" onclick="switchDetailTab('info', '${memberId}')">Info</div>
                        <div class="member-detail-tab" onclick="switchDetailTab('payments', '${memberId}')">Payments</div>
                        <div class="member-detail-tab" onclick="switchDetailTab('checkins', '${memberId}')">Check-ins</div>
                    </div>
                    <div id="member-detail-content">
                        <div class="detail-info-grid">
                            <div class="detail-info-item"><div class="label">Email</div><div class="value">${m.email}</div></div>
                            <div class="detail-info-item"><div class="label">Phone</div><div class="value">${m.phone}</div></div>
                            <div class="detail-info-item"><div class="label">Age</div><div class="value">${m.age || 'N/A'}</div></div>
                            <div class="detail-info-item"><div class="label">Gender</div><div class="value">${m.gender}</div></div>
                            <div class="detail-info-item"><div class="label">Plan</div><div class="value">${m.plan_name}</div></div>
                            <div class="detail-info-item"><div class="label">Membership End</div><div class="value">${formatDate(m.membership_end)}</div></div>
                            <div class="detail-info-item" style="grid-column:1/-1"><div class="label">Address</div><div class="value">${m.address || 'N/A'}</div></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-success" onclick="closeModal(); openRenewModal('${m.member_id}')">
                <i class="fas fa-sync-alt"></i> Renew
            </button>
            <button class="btn btn-danger" onclick="closeModal(); deleteMember('${m.member_id}', '${m.full_name}')">
                <i class="fas fa-trash"></i> Delete
            </button>
        </div>
    `;

    openModal(content, 'modal-lg');
}

async function switchDetailTab(tab, memberId) {
    document.querySelectorAll('.member-detail-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');

    const container = document.getElementById('member-detail-content');

    if (tab === 'info') {
        // Reload member to get fresh info
        const result = await apiGet(`/members/${memberId}`);
        if (result.success) {
            const m = result.data;
            container.innerHTML = `
                <div class="detail-info-grid">
                    <div class="detail-info-item"><div class="label">Email</div><div class="value">${m.email}</div></div>
                    <div class="detail-info-item"><div class="label">Phone</div><div class="value">${m.phone}</div></div>
                    <div class="detail-info-item"><div class="label">Age</div><div class="value">${m.age || 'N/A'}</div></div>
                    <div class="detail-info-item"><div class="label">Gender</div><div class="value">${m.gender}</div></div>
                    <div class="detail-info-item"><div class="label">Plan</div><div class="value">${m.plan_name}</div></div>
                    <div class="detail-info-item"><div class="label">Membership End</div><div class="value">${formatDate(m.membership_end)}</div></div>
                    <div class="detail-info-item" style="grid-column:1/-1"><div class="label">Address</div><div class="value">${m.address || 'N/A'}</div></div>
                </div>
            `;
        }
    } else if (tab === 'payments') {
        container.innerHTML = '<div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div>';
        const result = await apiGet(`/payments?member_id=${memberId}`);
        if (result.success && result.data?.length) {
            container.innerHTML = `
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Receipt</th><th>Plan</th><th>Amount</th><th>Method</th><th>Date</th><th>Status</th></tr></thead>
                        <tbody>${result.data.slice(0, 10).map(p => `
                            <tr>
                                <td><span class="badge badge-mono">${p.receipt_number}</span></td>
                                <td>${p.plan_name}</td>
                                <td><strong>${formatCurrency(p.amount)}</strong></td>
                                <td>${p.payment_method}</td>
                                <td>${formatDate(p.payment_date)}</td>
                                <td>${getPaymentStatusBadge(p.status)}</td>
                            </tr>
                        `).join('')}</tbody>
                    </table>
                </div>
            `;
        } else {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">💳</div><h3>No payments yet</h3></div>';
        }
    } else if (tab === 'checkins') {
        container.innerHTML = '<div class="skeleton skeleton-row"></div><div class="skeleton skeleton-row"></div>';
        const result = await apiGet(`/checkins/${memberId}`);
        if (result.success && result.data?.length) {
            container.innerHTML = result.data.slice(0, 10).map(c => `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <span class="timeline-name">${c.date}</span>
                    <span class="timeline-time">${formatTime(c.checkin_time)}</span>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><h3>No check-ins yet</h3></div>';
        }
    }
}

// ─── Renew Modal ─────────────────────────────────────────────
async function openRenewModal(memberId) {
    const [memberResult, plansResult] = await Promise.all([
        apiGet(`/members/${memberId}`),
        apiGet('/plans')
    ]);

    if (!memberResult.success) {
        showToast('Failed to load member', 'error');
        return;
    }

    const member = memberResult.data;
    const plans = plansResult.success ? plansResult.data : [];

    const planOptions = plans.map(p =>
        `<option value="${p._id}" data-price="${p.price}" ${p._id === member.plan_id ? 'selected' : ''}>${p.plan_name} - ${formatCurrency(p.price)} / ${p.duration_months}mo</option>`
    ).join('');

    const selectedPlan = plans.find(p => p._id === member.plan_id) || plans[0];

    const content = `
        <div class="modal-header">
            <h3><i class="fas fa-sync-alt" style="color:var(--success);margin-right:8px"></i> Renew Membership</h3>
            <button class="modal-close" onclick="closeModal()"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div style="background:var(--bg-primary);padding:16px;border-radius:var(--radius-md);margin-bottom:20px">
                <div style="font-weight:700;font-size:16px">${member.full_name}</div>
                <div style="font-size:13px;color:var(--text-secondary)">Current Plan: ${member.plan_name} · Expires: ${formatDate(member.membership_end)}</div>
            </div>

            <div class="form-group">
                <label>Select New Plan <span class="required">*</span></label>
                <select class="form-control" id="renew-plan" onchange="updateRenewAmount()">
                    ${planOptions}
                </select>
            </div>

            <div class="form-group">
                <label>Payment Method</label>
                <select class="form-control" id="renew-method">
                    <option value="Cash">Cash</option>
                    <option value="Card">Card</option>
                    <option value="UPI">UPI</option>
                </select>
            </div>

            <div class="form-group">
                <label>Amount</label>
                <input type="text" class="form-control" id="renew-amount" value="${formatCurrency(selectedPlan?.price || 0)}" readonly
                       style="background:var(--bg-primary);font-weight:700;font-size:18px;color:var(--primary)">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-success" id="renew-btn" onclick="submitRenewal('${memberId}')">
                <i class="fas fa-check"></i> Renew + Pay
            </button>
        </div>
    `;

    openModal(content);
}

function updateRenewAmount() {
    const select = document.getElementById('renew-plan');
    const option = select.options[select.selectedIndex];
    const price = option.dataset.price || 0;
    document.getElementById('renew-amount').value = formatCurrency(price);
}

async function submitRenewal(memberId) {
    const btn = document.getElementById('renew-btn');
    btn.innerHTML = '<div class="spinner"></div> Processing...';
    btn.disabled = true;

    try {
        const result = await apiPut(`/members/${memberId}/renew`, {
            plan_id: document.getElementById('renew-plan').value,
            payment_method: document.getElementById('renew-method').value
        });

        if (result.success) {
            showToast(result.message || 'Membership renewed! 🎉', 'success');
            closeModal();
            loadMembers();
        } else {
            showToast(result.error || 'Renewal failed', 'error');
            btn.innerHTML = '<i class="fas fa-check"></i> Renew + Pay';
            btn.disabled = false;
        }
    } catch (error) {
        showToast('Renewal error: ' + error.message, 'error');
        btn.innerHTML = '<i class="fas fa-check"></i> Renew + Pay';
        btn.disabled = false;
    }
}

// ─── Delete Member ───────────────────────────────────────────
function deleteMember(memberId, name) {
    showConfirm(
        'Delete Member',
        `Are you sure you want to delete <strong>${name}</strong> (${memberId})? This action cannot be undone.`,
        async () => {
            const result = await apiDelete(`/members/${memberId}`);
            if (result.success) {
                showToast(`Member ${memberId} deleted`, 'success');
                loadMembers();
            } else {
                showToast('Failed to delete: ' + (result.error || ''), 'error');
            }
        }
    );
}

// ═══════════════════════════════════════════════════════════════
// PAGE 3: PLANS
// ═══════════════════════════════════════════════════════════════

async function loadPlans() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header flex-between">
                <div>
                    <h2>Membership Plans</h2>
                    <p>Manage pricing and features</p>
                </div>
                <button class="btn btn-primary" onclick="togglePlanForm()">
                    <i class="fas fa-plus"></i> Add Plan
                </button>
            </div>

            <div class="plan-form-inline" id="plan-form">
                <h3 style="margin-bottom:16px;font-weight:700"><i class="fas fa-plus-circle" style="color:var(--primary);margin-right:8px"></i>Create New Plan</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Plan Name <span class="required">*</span></label>
                        <input type="text" class="form-control" id="plan-name" placeholder="e.g., Gold">
                    </div>
                    <div class="form-group">
                        <label>Duration (months) <span class="required">*</span></label>
                        <input type="number" class="form-control" id="plan-duration" min="1" placeholder="e.g., 6">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Price ($) <span class="required">*</span></label>
                        <input type="number" class="form-control" id="plan-price" min="0" step="0.01" placeholder="e.g., 149.00">
                    </div>
                    <div class="form-group">
                        <label>Features (comma-separated)</label>
                        <input type="text" class="form-control" id="plan-features" placeholder="Gym Access, Locker, PT Sessions">
                    </div>
                </div>
                <div style="display:flex;gap:12px;margin-top:8px">
                    <button class="btn btn-primary" onclick="submitPlan()">
                        <i class="fas fa-check"></i> Create Plan
                    </button>
                    <button class="btn btn-secondary" onclick="togglePlanForm()">Cancel</button>
                </div>
            </div>

            <div class="plans-grid" id="plans-grid">
                ${Array(3).fill('<div class="skeleton skeleton-card" style="height:400px"></div>').join('')}
            </div>
        </div>
    `;

    try {
        const result = await apiGet('/plans');
        if (result.success) {
            state.plans = result.data || [];
            renderPlansGrid();
        }
    } catch (error) {
        showToast('Failed to load plans', 'error');
    }
}

function renderPlansGrid() {
    const grid = document.getElementById('plans-grid');
    if (!grid) return;

    if (!state.plans.length) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1">
                <div class="empty-state-icon">💳</div>
                <h3>No plans created</h3>
                <p>Add your first membership plan</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = state.plans.map((plan, i) => renderPlanCard(plan, i === 1)).join('');
}

function renderPlanCard(plan, featured = false) {
    const featuresHtml = (plan.features || []).map(f =>
        `<li><i class="fas fa-check-circle"></i> ${f}</li>`
    ).join('');

    return `
        <div class="plan-card ${featured ? 'featured' : ''}">
            <div class="plan-card-name">${plan.plan_name}</div>
            <div class="plan-card-price">${formatCurrency(plan.price)} <span>USD</span></div>
            <div class="plan-card-duration">${plan.duration_months} month${plan.duration_months > 1 ? 's' : ''}</div>
            <ul class="plan-card-features">${featuresHtml}</ul>
            <button class="btn btn-primary" style="width:100%" onclick="editPlan('${plan._id}')">
                <i class="fas fa-edit"></i> Edit Plan
            </button>
        </div>
    `;
}

function togglePlanForm() {
    document.getElementById('plan-form').classList.toggle('active');
}

async function submitPlan() {
    const name = document.getElementById('plan-name').value.trim();
    const duration = document.getElementById('plan-duration').value;
    const price = document.getElementById('plan-price').value;
    const features = document.getElementById('plan-features').value;

    if (!name || !duration || !price) {
        showToast('Please fill in all required fields', 'warning');
        return;
    }

    try {
        const result = await apiPost('/plans', {
            plan_name: name,
            duration_months: parseInt(duration),
            price: parseFloat(price),
            features: features.split(',').map(f => f.trim()).filter(f => f)
        });

        if (result.success) {
            showToast(`Plan "${name}" created! 🎉`, 'success');
            togglePlanForm();
            loadPlans();
        } else {
            showToast(result.error || 'Failed to create plan', 'error');
        }
    } catch (error) {
        showToast('Error creating plan: ' + error.message, 'error');
    }
}

async function editPlan(planId) {
    const plan = state.plans.find(p => p._id === planId);
    if (!plan) return;

    const content = `
        <div class="modal-header">
            <h3><i class="fas fa-edit" style="color:var(--primary);margin-right:8px"></i> Edit Plan</h3>
            <button class="modal-close" onclick="closeModal()"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label>Plan Name</label>
                <input type="text" class="form-control" id="edit-plan-name" value="${plan.plan_name}">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Duration (months)</label>
                    <input type="number" class="form-control" id="edit-plan-duration" value="${plan.duration_months}">
                </div>
                <div class="form-group">
                    <label>Price ($)</label>
                    <input type="number" class="form-control" id="edit-plan-price" step="0.01" value="${plan.price}">
                </div>
            </div>
            <div class="form-group">
                <label>Features (comma-separated)</label>
                <input type="text" class="form-control" id="edit-plan-features" value="${(plan.features || []).join(', ')}">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" onclick="submitEditPlan('${planId}')">
                <i class="fas fa-save"></i> Save Changes
            </button>
        </div>
    `;

    openModal(content);
}

async function submitEditPlan(planId) {
    try {
        const result = await apiPut(`/plans/${planId}`, {
            plan_name: document.getElementById('edit-plan-name').value,
            duration_months: parseInt(document.getElementById('edit-plan-duration').value),
            price: parseFloat(document.getElementById('edit-plan-price').value),
            features: document.getElementById('edit-plan-features').value.split(',').map(f => f.trim()).filter(f => f)
        });

        if (result.success) {
            showToast('Plan updated!', 'success');
            closeModal();
            loadPlans();
        } else {
            showToast(result.error || 'Failed to update plan', 'error');
        }
    } catch (error) {
        showToast('Error updating plan: ' + error.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// PAGE 4: PAYMENTS
// ═══════════════════════════════════════════════════════════════

async function loadPayments() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header">
                <h2>Payments</h2>
                <p>Track revenue and payment history</p>
            </div>
            <div id="payment-summary" class="stats-grid stats-grid-3">
                ${Array(3).fill('<div class="skeleton skeleton-card" style="height:130px"></div>').join('')}
            </div>
            <div class="dashboard-grid-2">
                <div class="card" id="payments-table-card">
                    <div class="card-header"><h3>Payment History</h3></div>
                    <div class="card-body no-padding" id="payments-table-body">
                        ${Array(5).fill('<div class="skeleton skeleton-row" style="margin:0 16px"></div>').join('')}
                    </div>
                </div>
                <div class="card" id="payment-breakdown-card">
                    <div class="card-header"><h3>Payment Methods</h3></div>
                    <div class="card-body" id="payment-breakdown-body">
                        <div class="skeleton skeleton-card" style="height:200px"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    try {
        const [summaryResult, paymentsResult] = await Promise.all([
            apiGet('/payments/summary'),
            apiGet('/payments')
        ]);

        // Summary cards
        if (summaryResult.success) {
            const s = summaryResult.data;
            document.getElementById('payment-summary').innerHTML = `
                <div class="stat-card blue">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Total Revenue</span>
                        <div class="stat-card-icon blue"><i class="fas fa-dollar-sign"></i></div>
                    </div>
                    <div class="stat-card-value">${formatCurrency(s.total_revenue)}</div>
                </div>
                <div class="stat-card green">
                    <div class="stat-card-header">
                        <span class="stat-card-label">This Month</span>
                        <div class="stat-card-icon green"><i class="fas fa-calendar"></i></div>
                    </div>
                    <div class="stat-card-value">${formatCurrency(s.this_month_revenue)}</div>
                </div>
                <div class="stat-card purple">
                    <div class="stat-card-header">
                        <span class="stat-card-label">Average Payment</span>
                        <div class="stat-card-icon purple"><i class="fas fa-chart-bar"></i></div>
                    </div>
                    <div class="stat-card-value">${formatCurrency(s.average_payment)}</div>
                </div>
            `;

            // Payment method breakdown
            renderPaymentBreakdown(s.payments_by_method, s.total_revenue);
        }

        // Payments table
        if (paymentsResult.success) {
            state.payments = paymentsResult.data || [];
            renderPaymentsTable();
        }

    } catch (error) {
        showToast('Failed to load payments', 'error');
    }
}

function renderPaymentsTable() {
    const container = document.getElementById('payments-table-body');
    if (!container) return;

    if (!state.payments.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">💰</div><h3>No payments yet</h3><p>Payments will appear here after members enroll</p></div>';
        return;
    }

    container.innerHTML = `
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Receipt</th>
                        <th>Member</th>
                        <th>Plan</th>
                        <th>Amount</th>
                        <th>Method</th>
                        <th>Date</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${state.payments.map(p => renderPaymentRow(p)).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderPaymentRow(payment) {
    return `
        <tr>
            <td><span class="badge badge-mono">${payment.receipt_number}</span></td>
            <td><strong>${payment.member_name}</strong></td>
            <td><span class="badge badge-plan">${payment.plan_name}</span></td>
            <td><strong>${formatCurrency(payment.amount)}</strong></td>
            <td>${payment.payment_method}</td>
            <td>${formatDate(payment.payment_date)}</td>
            <td>${getPaymentStatusBadge(payment.status)}</td>
        </tr>
    `;
}

function renderPaymentBreakdown(methods, totalRevenue) {
    const container = document.getElementById('payment-breakdown-body');
    if (!container) return;

    if (!methods || !Object.keys(methods).length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><h3>No data yet</h3></div>';
        return;
    }

    const total = totalRevenue || 1;
    const barsHtml = Object.entries(methods).map(([method, data]) => {
        const pct = Math.round((data.total / total) * 100);
        const cls = method.toLowerCase();
        return `
            <div class="payment-bar-item">
                <span class="payment-bar-label">${method}</span>
                <div class="payment-bar-track">
                    <div class="payment-bar-fill ${cls}" style="width:${pct}%">${pct}%</div>
                </div>
                <span class="payment-bar-amount">${formatCurrency(data.total)}</span>
            </div>
        `;
    }).join('');

    container.innerHTML = barsHtml;
}

// ═══════════════════════════════════════════════════════════════
// PAGE 5: CHECK-IN
// ═══════════════════════════════════════════════════════════════

async function loadCheckins() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header text-center">
                <h2>Member Check-In</h2>
                <p>Scan or search to check in members</p>
            </div>

            <div class="checkin-hero">
                <div class="checkin-hero-icon"><i class="fas fa-qrcode"></i></div>
                <div class="checkin-search-wrapper">
                    <i class="fas fa-search checkin-search-icon"></i>
                    <input type="text" class="checkin-search" id="checkin-input"
                           placeholder="Enter Member ID or Name to Check In"
                           oninput="searchCheckinMember(this.value)"
                           onkeypress="if(event.key==='Enter') submitCheckin()">
                    <div class="checkin-suggestions" id="checkin-suggestions"></div>
                </div>
                <div id="checkin-result"></div>
            </div>

            <div class="card" style="max-width:600px;margin:0 auto">
                <div class="card-header">
                    <h3><i class="fas fa-clock" style="color:var(--primary);margin-right:8px"></i> Today's Check-ins</h3>
                    <span class="badge badge-plan" id="checkin-count">0</span>
                </div>
                <div class="card-body" id="today-checkins">
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                </div>
            </div>
        </div>
    `;

    await loadTodayCheckins();
}

async function loadTodayCheckins() {
    try {
        const result = await apiGet('/checkins/today');
        const container = document.getElementById('today-checkins');
        const countBadge = document.getElementById('checkin-count');

        if (!container) return;

        if (result.success && result.data?.length) {
            countBadge.textContent = result.data.length;
            container.innerHTML = result.data.map(c => `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <span class="timeline-name">${c.member_name}</span>
                    <span class="timeline-time">${formatTime(c.checkin_time)}</span>
                </div>
            `).join('');
        } else {
            countBadge.textContent = '0';
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><h3>No check-ins today yet</h3><p>Members will appear here after checking in</p></div>';
        }
    } catch (error) {
        console.error('Error loading today checkins:', error);
    }
}

let checkinSearchDebounce = null;
async function searchCheckinMember(query) {
    const suggestions = document.getElementById('checkin-suggestions');

    clearTimeout(checkinSearchDebounce);

    if (!query || query.length < 2) {
        suggestions.classList.remove('active');
        return;
    }

    checkinSearchDebounce = setTimeout(async () => {
        try {
            const result = await apiGet(`/members?search=${encodeURIComponent(query)}`);
            if (result.success && result.data?.length) {
                suggestions.innerHTML = result.data.slice(0, 5).map(m => `
                    <div class="suggestion-item" onclick="selectCheckinMember('${m.member_id}', '${m.full_name}')">
                        <div class="member-avatar-placeholder" style="background:${getAvatarColor(m.full_name)};width:36px;height:36px;border-radius:8px;font-size:14px;display:flex;align-items:center;justify-content:center;color:white;font-weight:700">${getInitials(m.full_name)}</div>
                        <div>
                            <div class="name">${m.full_name}</div>
                            <div class="id">${m.member_id} · ${m.status}</div>
                        </div>
                    </div>
                `).join('');
                suggestions.classList.add('active');
            } else {
                suggestions.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted)">No members found</div>';
                suggestions.classList.add('active');
            }
        } catch (error) {
            suggestions.classList.remove('active');
        }
    }, 300);
}

function selectCheckinMember(memberId, name) {
    document.getElementById('checkin-input').value = memberId;
    document.getElementById('checkin-suggestions').classList.remove('active');
    checkInMember(memberId);
}

async function submitCheckin() {
    const input = document.getElementById('checkin-input');
    if (input.value.trim()) {
        await checkInMember(input.value.trim());
    }
}

async function checkInMember(memberId) {
    const resultContainer = document.getElementById('checkin-result');
    const suggestions = document.getElementById('checkin-suggestions');
    suggestions.classList.remove('active');

    try {
        const result = await apiPost('/checkins', { member_id: memberId });

        if (result.success) {
            const days = result.days_remaining;
            resultContainer.innerHTML = `
                <div class="checkin-result success">
                    <div class="result-icon"><i class="fas fa-check"></i></div>
                    <h3>Welcome back, ${result.member_name}! 💪</h3>
                    <p><span class="badge badge-plan">${result.plan_name}</span></p>
                    <p>Membership expires: ${formatDate(result.membership_end)}</p>
                    <p style="font-weight:700;color:var(--success)">Membership expires in ${days} day${days !== 1 ? 's' : ''}</p>
                </div>
            `;
            showToast(`${result.member_name} checked in! 💪`, 'success');
            await loadTodayCheckins();

            // Auto-clear after 4 seconds
            if (state.checkinTimeout) clearTimeout(state.checkinTimeout);
            state.checkinTimeout = setTimeout(() => {
                resultContainer.innerHTML = '';
                document.getElementById('checkin-input').value = '';
            }, 4000);
        } else {
            if (result.expired) {
                resultContainer.innerHTML = `
                    <div class="checkin-result error">
                        <div class="result-icon"><i class="fas fa-times"></i></div>
                        <h3>Membership Expired ❌</h3>
                        <p>${result.member_name || 'Member'}</p>
                        <p style="font-weight:600;color:var(--danger)">Please renew at reception</p>
                    </div>
                `;
            } else {
                resultContainer.innerHTML = `
                    <div class="checkin-result error">
                        <div class="result-icon"><i class="fas fa-exclamation"></i></div>
                        <h3>Check-in Failed</h3>
                        <p>${result.error || 'Unknown error'}</p>
                    </div>
                `;
            }

            if (state.checkinTimeout) clearTimeout(state.checkinTimeout);
            state.checkinTimeout = setTimeout(() => {
                resultContainer.innerHTML = '';
                document.getElementById('checkin-input').value = '';
            }, 4000);
        }
    } catch (error) {
        showToast('Check-in error: ' + error.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// PAGE 6: AWS PANEL
// ═══════════════════════════════════════════════════════════════

async function loadAWSPanel() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header">
                <h2><i class="fas fa-cloud" style="color:var(--primary);margin-right:8px"></i> AWS Panel</h2>
                <p>Cloud infrastructure status and management</p>
            </div>
            <div class="aws-grid" id="aws-panels">
                ${Array(3).fill('<div class="skeleton skeleton-card" style="height:350px"></div>').join('')}
            </div>
            <div id="aws-security-note"></div>
        </div>
    `;

    try {
        const [secretsResult, s3Result, kmsResult] = await Promise.all([
            apiGet('/aws/secrets-info'),
            apiGet('/aws/s3-info'),
            apiGet('/aws/kms-info')
        ]);

        let panelsHtml = '';

        // Card 1: Secrets Manager
        if (secretsResult.success) {
            const s = secretsResult.data;
            const keysHtml = (s.available_keys || []).map(k =>
                `<span class="badge badge-mono">${k}</span>`
            ).join('');
            const cacheInfo = s.cache_info || {};

            panelsHtml += `
                <div class="aws-card">
                    <div class="aws-card-header">
                        <i class="fas fa-key"></i>
                        <h3>Secrets Manager</h3>
                    </div>
                    <div class="aws-card-body">
                        <div class="aws-info-row">
                            <span class="aws-info-label">Secret Name</span>
                            <span class="aws-info-value">${s.secret_name || 'N/A'}</span>
                        </div>
                        <div class="aws-info-row">
                            <span class="aws-info-label">MongoDB URI</span>
                            <span class="aws-info-value">${s.mongodb_uri_preview || 'N/A'}</span>
                        </div>
                        <div class="aws-info-row">
                            <span class="aws-info-label">S3 Bucket</span>
                            <span class="aws-info-value">${s.s3_bucket_name || 'N/A'}</span>
                        </div>
                        <div class="aws-info-row">
                            <span class="aws-info-label">Cached Secrets</span>
                            <span class="aws-info-value">${cacheInfo.total_cached_secrets || 0}</span>
                        </div>
                        <div class="aws-info-row">
                            <span class="aws-info-label">Cache TTL</span>
                            <span class="aws-info-value">${cacheInfo.ttl_seconds || 300}s</span>
                        </div>
                        <div style="margin-top:12px;font-size:12px;color:var(--text-muted);font-weight:600">Available Keys:</div>
                        <div class="aws-keys-list">${keysHtml || '<span class="text-muted">None</span>'}</div>
                        <button class="btn btn-secondary btn-sm mt-2" onclick="clearAllCaches()">
                            <i class="fas fa-sync"></i> Clear Cache
                        </button>
                    </div>
                </div>
            `;
        } else {
            panelsHtml += renderAWSErrorCard('Secrets Manager', 'fa-key', secretsResult.error);
        }

        // Card 2: S3 + KMS
        const s3Data = s3Result.success ? s3Result.data : {};
        const kmsData = kmsResult.success ? kmsResult.data : {};

        panelsHtml += `
            <div class="aws-card">
                <div class="aws-card-header">
                    <i class="fas fa-database"></i>
                    <h3>S3 + KMS</h3>
                </div>
                <div class="aws-card-body">
                    <div class="aws-info-row">
                        <span class="aws-info-label">Bucket Name</span>
                        <span class="aws-info-value">${s3Data.bucket_name || 'N/A'}</span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">Region</span>
                        <span class="aws-info-value">${s3Data.bucket_region || 'N/A'}</span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">Total Photos</span>
                        <span class="aws-info-value">${s3Data.total_photos || 0}</span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">Encryption</span>
                        <span class="aws-info-value"><span class="badge badge-active">${s3Data.encryption || 'SSE-KMS'}</span></span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">KMS Key Alias</span>
                        <span class="aws-info-value">${kmsData.key_alias || 'N/A'}</span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">KMS Key State</span>
                        <span class="aws-info-value">
                            <span class="badge ${kmsData.key_state === 'Enabled' ? 'badge-active' : 'badge-expired'}">
                                ${kmsData.key_state || 'Unknown'}
                            </span>
                        </span>
                    </div>
                </div>
            </div>
        `;

        // Card 3: SNS
        const healthData = state.healthData;
        const snsPreview = healthData?.services?.sns?.topic_preview || 'N/A';

        panelsHtml += `
            <div class="aws-card">
                <div class="aws-card-header">
                    <i class="fas fa-bell"></i>
                    <h3>SNS Notifications</h3>
                </div>
                <div class="aws-card-body">
                    <div class="aws-info-row">
                        <span class="aws-info-label">Topic ARN</span>
                        <span class="aws-info-value">${snsPreview}</span>
                    </div>
                    <div class="aws-info-row">
                        <span class="aws-info-label">Status</span>
                        <span class="aws-info-value">
                            <span class="badge ${healthData?.services?.sns?.healthy ? 'badge-active' : 'badge-expired'}">
                                ${healthData?.services?.sns?.healthy ? 'Active' : 'Inactive'}
                            </span>
                        </span>
                    </div>
                    <div style="margin-top:20px">
                        <button class="btn btn-warning" id="sns-alert-btn" onclick="sendExpiryAlertsAWS()">
                            <i class="fas fa-bell"></i> Send Expiry Alerts Now
                        </button>
                        <div id="sns-alert-result" style="margin-top:12px"></div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('aws-panels').innerHTML = panelsHtml;

        // Security note
        document.getElementById('aws-security-note').innerHTML = `
            <div class="security-note">
                <i class="fas fa-shield-alt"></i>
                <p>
                    <strong>Security:</strong> All member photos are encrypted with AWS KMS (SSE-KMS).
                    Credentials are managed by AWS Secrets Manager and never stored in application code.
                    IAM roles are used for EC2 access — zero hardcoded credentials.
                </p>
            </div>
        `;

    } catch (error) {
        showToast('Failed to load AWS panel', 'error');
    }
}

function renderAWSErrorCard(title, icon, error) {
    return `
        <div class="aws-card">
            <div class="aws-card-header"><i class="fas ${icon}"></i><h3>${title}</h3></div>
            <div class="aws-card-body">
                <div class="empty-state"><div class="empty-state-icon">⚠️</div>
                <h3>Not Available</h3><p>${error || 'Could not connect to service'}</p></div>
            </div>
        </div>
    `;
}

async function clearAllCaches() {
    try {
        const result = await apiPost('/aws/cache/clear', {});
        if (result.success) {
            showToast('All caches cleared! ♻️', 'success');
            loadAWSPanel();
        } else {
            showToast('Failed to clear cache', 'error');
        }
    } catch (error) {
        showToast('Cache clear error: ' + error.message, 'error');
    }
}

async function sendExpiryAlertsAWS() {
    const btn = document.getElementById('sns-alert-btn');
    btn.innerHTML = '<div class="spinner"></div> Sending...';
    btn.disabled = true;

    try {
        const result = await apiPost('/aws/send-expiry-alerts', {});
        const resultDiv = document.getElementById('sns-alert-result');

        if (result.success) {
            resultDiv.innerHTML = `
                <div style="padding:12px;background:var(--success-bg);border-radius:var(--radius-sm);color:var(--success);font-weight:600;font-size:14px">
                    ✅ ${result.data?.alerts_sent || 0} alert(s) sent at ${new Date().toLocaleTimeString()}
                </div>
            `;
            showToast(`${result.data?.alerts_sent || 0} expiry alerts sent`, 'success');
        } else {
            resultDiv.innerHTML = `
                <div style="padding:12px;background:var(--danger-bg);border-radius:var(--radius-sm);color:var(--danger);font-size:14px">
                    ❌ Failed: ${result.error || 'Unknown error'}
                </div>
            `;
        }
    } catch (error) {
        showToast('Failed to send alerts', 'error');
    }

    btn.innerHTML = '<i class="fas fa-bell"></i> Send Expiry Alerts Now';
    btn.disabled = false;
}

// ═══════════════════════════════════════════════════════════════
// PAGE 7: SETTINGS
// ═══════════════════════════════════════════════════════════════

async function loadSettings() {
    const main = document.getElementById('main-content');
    main.innerHTML = `
        <div class="page-content">
            <div class="page-header">
                <h2><i class="fas fa-cog" style="color:var(--primary);margin-right:8px"></i> Settings</h2>
                <p>Application configuration</p>
            </div>
            <div class="card settings-card">
                <div class="card-header"><h3>Gym Information</h3></div>
                <div class="card-body" id="settings-body">
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                </div>
            </div>
        </div>
    `;

    try {
        const [healthResult, secretsResult] = await Promise.all([
            apiGet('/health'),
            apiGet('/aws/secrets-info')
        ]);

        const gymName = secretsResult.success ? (secretsResult.data?.gym_name || 'GymVault Fitness Center') : 'GymVault Fitness Center';
        const version = healthResult.success ? healthResult.data?.version : '1.0.0';

        document.getElementById('settings-body').innerHTML = `
            <div class="settings-item">
                <span class="label">Gym Name</span>
                <span class="value">${gymName}</span>
            </div>
            <div class="settings-item">
                <span class="label">App Version</span>
                <span class="value">v${version}</span>
            </div>
            <div class="settings-item">
                <span class="label">API Endpoint</span>
                <span class="value" style="font-family:monospace;font-size:12px">${API}</span>
            </div>
            <div class="settings-item">
                <span class="label">MongoDB</span>
                <span class="value">
                    <span class="badge ${healthResult.data?.services?.mongodb?.healthy ? 'badge-active' : 'badge-expired'}">
                        ${healthResult.data?.services?.mongodb?.status || 'Unknown'}
                    </span>
                </span>
            </div>
            <div class="settings-item">
                <span class="label">Secret Name</span>
                <span class="value" style="font-family:monospace;font-size:12px">${secretsResult.data?.secret_name || 'gymvault/config'}</span>
            </div>
            <div class="settings-item">
                <span class="label">Health Check Interval</span>
                <span class="value">Every 30 seconds</span>
            </div>
        `;
    } catch (error) {
        showToast('Failed to load settings', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    navigateTo('dashboard');

    // Health check every 30 seconds
    setInterval(checkHealth, 30000);
});
