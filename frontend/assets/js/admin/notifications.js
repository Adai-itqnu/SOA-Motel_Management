/**
 * Admin Notifications Page JavaScript
 * Clean version - using TailwindCSS layout
 */

let allNotifications = [];
let allUsers = [];
let isLoading = false;

document.addEventListener("DOMContentLoaded", function () {
  // Initialize admin layout (sidebar)
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  loadNotifications();
  loadUsers();
  initEventListeners();
});

function initEventListeners() {
  // Character counters
  const titleInput = document.getElementById("notificationTitle");
  const messageInput = document.getElementById("notificationMessage");

  if (titleInput) {
    titleInput.addEventListener("input", function () {
      document.getElementById("titleCount").textContent = this.value.length;
    });
  }

  if (messageInput) {
    messageInput.addEventListener("input", function () {
      document.getElementById("messageCount").textContent = this.value.length;
    });
  }
}

async function loadNotifications() {
  if (isLoading) return;
  isLoading = true;
  showLoading(true);

  try {
    const response = await fetch("/api/notifications/admin", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) throw new Error("Failed to load notifications");

    const data = await response.json();
    allNotifications = data.notifications || [];

    updateStats();
    renderNotifications();
  } catch (error) {
    console.error("Error loading notifications:", error);
    displayToast("Không thể tải danh sách thông báo", "error");
  } finally {
    showLoading(false);
    isLoading = false;
  }
}

async function loadUsers() {
  try {
    const response = await fetch("/api/users", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) throw new Error("Failed to load users");

    const data = await response.json();
    allUsers = data.users || [];

    populateUserSelect();
  } catch (error) {
    console.error("Error loading users:", error);
  }
}

function populateUserSelect() {
  const select = document.getElementById("targetUser");
  if (!select) return;

  select.innerHTML = '<option value="">Chọn người dùng...</option>';

  allUsers.forEach((user) => {
    const option = document.createElement("option");
    option.value = user.id || user._id;
    option.textContent = `${user.fullname || user.username} (${user.email})`;
    select.appendChild(option);
  });
}

function updateStats() {
  const total = allNotifications.length;
  const broadcast = allNotifications.filter(
    (n) => n.metadata?.broadcast === true
  ).length;
  const personal = allNotifications.filter(
    (n) =>
      n.metadata?.broadcast !== true &&
      n.type !== "welcome" &&
      n.type !== "reminder"
  ).length;
  const reminder = allNotifications.filter(
    (n) =>
      n.type === "reminder" ||
      n.type === "rent_due_today" ||
      n.type === "rent_due_soon" ||
      n.type === "rent_overdue"
  ).length;

  setText("totalNotifications", total);
  setText("broadcastCount", broadcast);
  setText("personalCount", personal);
  setText("reminderCount", reminder);
}

function renderNotifications() {
  const container = document.getElementById("notificationsList");
  const emptyState = document.getElementById("emptyState");
  const filterType = document.getElementById("filterType")?.value || "";

  if (!container) return;

  let filtered = [...allNotifications];

  // Apply filter
  if (filterType) {
    filtered = filtered.filter((n) => {
      if (filterType === "broadcast") return n.metadata?.broadcast === true;
      if (filterType === "personal")
        return n.metadata?.broadcast !== true && n.type !== "welcome";
      return n.type === filterType;
    });
  }

  // Sort by date (newest first)
  filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  if (filtered.length === 0) {
    container.innerHTML = "";
    if (emptyState) emptyState.style.display = "block";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  container.innerHTML = filtered
    .map((notification) => renderNotificationItem(notification))
    .join("");
}

function renderNotificationItem(notification) {
  const typeBadge = getTypeBadge(notification);
  const timeAgo = formatTimeAgo(notification.created_at);
  const userName = getUserName(notification.user_id);
  const isRead = notification.status === "read";

  return `
        <div class="p-4 mb-3 rounded-xl border border-gray-100 hover:shadow-md transition-all ${
          isRead ? "bg-white" : "bg-indigo-50/50"
        }">
            <div class="flex justify-between items-start mb-2">
                <div>
                    <h4 class="font-semibold text-gray-800">${escapeHtml(
                      notification.title || "Không có tiêu đề"
                    )}</h4>
                    ${typeBadge}
                </div>
            </div>
            <p class="text-gray-600 text-sm mb-3">${escapeHtml(
              notification.message || ""
            )}</p>
            <div class="flex flex-wrap gap-4 text-xs text-gray-400">
                <span>👤 ${
                  notification.metadata?.broadcast
                    ? "Tất cả người dùng"
                    : userName
                }</span>
                <span>🕐 ${timeAgo}</span>
                <span>${isRead ? "✅ Đã đọc" : "📩 Chưa đọc"}</span>
            </div>
        </div>
    `;
}

function getTypeBadge(notification) {
  const type = notification.type || "info";
  const isBroadcast = notification.metadata?.broadcast === true;

  if (isBroadcast) {
    return '<span class="inline-block mt-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">Gửi toàn bộ</span>';
  }

  const badges = {
    welcome:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">Chào mừng</span>',
    reminder:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">Nhắc nhở</span>',
    rent_due_today:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Đến hạn</span>',
    rent_due_soon:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">Sắp đến hạn</span>',
    rent_overdue:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Quá hạn</span>',
    warning:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">Cảnh báo</span>',
    important:
      '<span class="inline-block mt-1 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Quan trọng</span>',
  };

  return (
    badges[type] ||
    '<span class="inline-block mt-1 px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">Cá nhân</span>'
  );
}

function getUserName(userId) {
  if (!userId) return "N/A";
  const user = allUsers.find((u) => (u.id || u._id) === userId);
  return user ? user.fullname || user.username : userId;
}

// Modal functions
function openSendModal() {
  document.getElementById("sendModal").classList.remove("hidden");
  resetForm();
}

function closeSendModal() {
  document.getElementById("sendModal").classList.add("hidden");
}

function toggleUserSelect() {
  const targetType = document.getElementById("targetType").value;
  const userGroup = document.getElementById("userSelectGroup");
  if (userGroup) {
    userGroup.style.display = targetType === "user" ? "block" : "none";
  }
}

async function sendNotification(event) {
  event.preventDefault();

  const targetType = document.getElementById("targetType").value;
  const targetUser = document.getElementById("targetUser").value;
  const title = document.getElementById("notificationTitle").value.trim();
  const message = document.getElementById("notificationMessage").value.trim();
  const type = document.getElementById("notificationType").value;

  // Validation
  if (!title || !message) {
    displayToast("Vui lòng điền đầy đủ tiêu đề và nội dung", "error");
    return;
  }

  if (targetType === "user" && !targetUser) {
    displayToast("Vui lòng chọn người dùng", "error");
    return;
  }

  const payload = {
    title,
    message,
    type,
    broadcast: targetType === "all",
  };

  if (targetType === "user") {
    payload.user_id = targetUser;
  }

  showLoading(true);

  try {
    const response = await fetch("/api/notifications/send", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || "Failed to send notification");
    }

    displayToast("Gửi thông báo thành công!", "success");
    closeSendModal();
    loadNotifications();
  } catch (error) {
    console.error("Error sending notification:", error);
    displayToast(error.message || "Không thể gửi thông báo", "error");
  } finally {
    showLoading(false);
  }
}

function resetForm() {
  const form = document.getElementById("sendNotificationForm");
  if (form) form.reset();

  const userGroup = document.getElementById("userSelectGroup");
  if (userGroup) userGroup.style.display = "none";

  setText("titleCount", "0");
  setText("messageCount", "0");
}

// Helper functions
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatTimeAgo(dateString) {
  if (!dateString) return "N/A";

  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return "Vừa xong";
  if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} ngày trước`;

  return date.toLocaleDateString("vi-VN");
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showLoading(show) {
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) {
    overlay.style.display = show ? "flex" : "none";
  }
}

function getToken() {
  return localStorage.getItem("token") || "";
}

function displayToast(message, type = "info") {
  // Remove existing toast if any
  const existingToast = document.getElementById("customToast");
  if (existingToast) existingToast.remove();
  
  // Create toast element
  const toast = document.createElement("div");
  toast.id = "customToast";
  
  // Colors based on type
  const colors = {
    success: "bg-green-500",
    error: "bg-red-500",
    warning: "bg-amber-500",
    info: "bg-blue-500"
  };
  
  const icons = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ"
  };
  
  const bgColor = colors[type] || colors.info;
  const icon = icons[type] || icons.info;
  
  toast.className = `fixed top-4 right-4 z-50 ${bgColor} text-white px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 animate-slide-in`;
  toast.innerHTML = `
    <span class="text-xl font-bold">${icon}</span>
    <span class="font-medium">${message}</span>
  `;
  
  // Add animation style
  const style = document.createElement("style");
  style.textContent = `
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .animate-slide-in { animation: slideIn 0.3s ease-out; }
  `;
  document.head.appendChild(style);
  
  document.body.appendChild(toast);
  
  // Auto remove after 4 seconds
  setTimeout(() => {
    toast.style.transition = "opacity 0.3s";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
