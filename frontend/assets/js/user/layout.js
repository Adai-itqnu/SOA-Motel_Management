/**
 * Layout Manager - Shared header and footer for all user pages
 * This script injects the header and footer HTML into each page
 */
(function () {
  "use strict";

  const Layout = {
    currentPage: null,

    // Header HTML template
    getHeaderHTML() {
      return `
    <header class="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-gray-100 shadow-sm">
      <div class="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex h-16 items-center justify-between gap-4">
          <!-- Logo -->
          <a href="/user/home.html" class="flex items-center gap-2">
            <div class="size-9 bg-primary rounded-xl flex items-center justify-center text-white shadow-lg shadow-primary/20">
              <span class="material-symbols-outlined">apartment</span>
            </div>
            <span class="text-lg font-bold tracking-tight text-gray-900 hidden sm:block">MotelHDK</span>
          </a>

          <!-- Nav Tabs (Desktop) -->
          <nav id="desktopNav" class="hidden md:flex items-center gap-1 text-sm font-semibold">
            <a href="/user/home.html" data-nav="home" class="nav-link px-4 py-2 rounded-lg flex items-center gap-2 transition-colors">
              <span class="material-symbols-outlined text-[20px]">home</span>
              Trang chủ
            </a>
            <a href="/user/my-room.html" data-nav="my-room" class="nav-link px-4 py-2 rounded-lg flex items-center gap-2 transition-colors">
              <span class="material-symbols-outlined text-[20px]">meeting_room</span>
              Phòng của tôi
            </a>
            <a href="/user/bills.html" data-nav="bills" class="nav-link px-4 py-2 rounded-lg flex items-center gap-2 transition-colors">
              <span class="material-symbols-outlined text-[20px]">receipt_long</span>
              Hóa đơn
            </a>
          </nav>

          <!-- User Menu + Notifications -->
          <div class="flex items-center gap-3">
            <!-- Notification Bell -->
            <div class="relative">
              <button id="notifBell" class="flex items-center justify-center size-10 rounded-full border border-gray-200 bg-gray-50 hover:bg-gray-100 transition" aria-label="Thông báo">
                <span class="material-symbols-outlined text-[20px] text-gray-700">notifications</span>
                <span id="notifBadge" class="hidden absolute -top-1 -right-1 rounded-full bg-primary text-white text-[10px] font-bold px-1.5 py-0.5 min-w-[18px] text-center"></span>
              </button>
              <div id="notifDropdown" class="dropdown-menu absolute right-0 top-12 w-80 bg-white border border-gray-100 rounded-xl shadow-2xl z-50">
                <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <span class="font-semibold text-gray-900">Thông báo</span>
                  <span id="notifStatus" class="text-xs text-gray-500">Chưa có thông báo</span>
                </div>
                <div id="notifList" class="max-h-80 overflow-y-auto"></div>
              </div>
            </div>

            <!-- User Menu -->
            <div class="relative">
              <button id="userMenuBtn" class="flex items-center gap-2 p-1.5 pr-3 rounded-full border border-gray-200 bg-gray-50 hover:bg-gray-100 transition">
                <div id="userAvatar" class="size-9 rounded-full bg-primary text-white font-bold flex items-center justify-center text-sm">U</div>
                <div class="hidden sm:block text-left">
                  <p id="userName" class="text-sm font-semibold text-gray-900 max-w-[120px] truncate">User</p>
                  <p class="text-xs text-gray-500">Người thuê</p>
                </div>
                <span class="material-symbols-outlined text-gray-500 text-[18px] hidden sm:block">expand_more</span>
              </button>
              <div id="userDropdown" class="dropdown-menu absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-2xl border border-gray-100 py-2 z-50">
                <div class="px-4 py-3 border-b border-gray-100">
                  <p id="dropdownName" class="font-semibold text-gray-900">User</p>
                  <p id="dropdownEmail" class="text-sm text-gray-500 truncate">email@example.com</p>
                </div>
                <div class="py-2">
                  <a href="/user/profile.html" class="flex items-center gap-3 px-4 py-2.5 text-gray-700 hover:bg-gray-50 transition">
                    <span class="material-symbols-outlined text-gray-400">account_circle</span>
                    Thông tin cá nhân
                  </a>
                  <a href="/user/bills.html" class="flex items-center gap-3 px-4 py-2.5 text-gray-700 hover:bg-gray-50 transition">
                    <span class="material-symbols-outlined text-gray-400">history</span>
                    Lịch sử thanh toán
                  </a>
                </div>
                <div class="border-t border-gray-100 pt-2">
                  <button id="logoutBtn" class="flex items-center gap-3 px-4 py-2.5 text-red-600 hover:bg-red-50 w-full transition">
                    <span class="material-symbols-outlined">logout</span>
                    Đăng xuất
                  </button>
                </div>
              </div>
            </div>

            <!-- Mobile Menu Button -->
            <button id="mobileMenuBtn" class="md:hidden flex items-center justify-center size-10 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100">
              <span class="material-symbols-outlined">menu</span>
            </button>
          </div>
        </div>

        <!-- Mobile Nav -->
        <nav id="mobileNav" class="hidden md:hidden pb-4 pt-2 border-t border-gray-100 mt-2">
          <div class="flex flex-col gap-1">
            <a href="/user/home.html" data-nav="home" class="nav-link-mobile flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-gray-50 transition">
              <span class="material-symbols-outlined text-[20px]">home</span>
              <span class="font-medium">Trang chủ</span>
            </a>
            <a href="/user/my-room.html" data-nav="my-room" class="nav-link-mobile flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-gray-50 transition">
              <span class="material-symbols-outlined text-[20px]">meeting_room</span>
              <span class="font-medium">Phòng của tôi</span>
            </a>
            <a href="/user/bills.html" data-nav="bills" class="nav-link-mobile flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-gray-50 transition">
              <span class="material-symbols-outlined text-[20px]">receipt_long</span>
              <span class="font-medium">Hóa đơn</span>
            </a>
          </div>
        </nav>
      </div>
    </header>`;
    },

    // Footer HTML template
    getFooterHTML() {
      return `
    <footer class="mt-auto border-t border-gray-100 bg-white">
      <div class="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4">
          <div class="flex items-center gap-2">
            <div class="size-8 bg-primary rounded-lg flex items-center justify-center text-white">
              <span class="material-symbols-outlined text-[18px]">apartment</span>
            </div>
            <span class="text-sm font-semibold text-gray-900">MotelHDK</span>
          </div>
          <div class="flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500">
            <a href="#" class="hover:text-primary transition-colors">Điều khoản</a>
            <a href="#" class="hover:text-primary transition-colors">Chính sách</a>
            <a href="#" class="hover:text-primary transition-colors">Hỗ trợ</a>
          </div>
          <p class="text-sm text-gray-400">© 2025 MotelHDK. All rights reserved.</p>
        </div>
      </div>
    </footer>`;
    },

    // CSS styles for layout
    getStyles() {
      return `
    <style id="layout-styles">
      .dropdown-menu {
        opacity: 0;
        visibility: hidden;
        transform: translateY(-6px);
        transition: all 0.18s ease;
      }
      .dropdown-menu.show {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
      }
      .nav-link.active, .nav-link-mobile.active {
        background: #ea2a33;
        color: #fff;
      }
      .nav-link:not(.active) {
        color: #4b5563;
      }
      .nav-link:not(.active):hover {
        background: #f3f4f6;
      }
      .nav-link-mobile:not(.active) {
        color: #374151;
      }
      .nav-link-mobile.active {
        background: rgba(234, 42, 51, 0.1);
        color: #ea2a33;
      }
    </style>`;
    },

    // Initialize layout
    init(pageName) {
      this.currentPage = pageName || this.detectCurrentPage();

      // Inject styles if not already present
      if (!document.getElementById("layout-styles")) {
        document.head.insertAdjacentHTML("beforeend", this.getStyles());
      }

      // Inject header first (before auth check)
      const headerPlaceholder = document.getElementById("layout-header");
      if (headerPlaceholder) {
        headerPlaceholder.outerHTML = this.getHeaderHTML();
      }

      // Inject footer
      const footerPlaceholder = document.getElementById("layout-footer");
      if (footerPlaceholder) {
        footerPlaceholder.outerHTML = this.getFooterHTML();
      }

      // Check auth - if not logged in, redirect (but header/footer already injected)
      if (!this.checkAuth()) return;

      // Load user info
      this.loadUserInfo();

      // Setup navigation active state
      this.setupNavigation();

      // Setup dropdowns
      this.setupUserDropdown();
      this.setupNotifications();
      this.setupMobileMenu();

      // Setup logout
      this.setupLogout();
    },

    // Check authentication
    checkAuth() {
      if (typeof Auth === "undefined") {
        console.error("Auth module not loaded");
        return false;
      }
      if (!Auth.isLoggedIn()) {
        window.location.href = "/auth/login.html";
        return false;
      }
      return true;
    },

    // Detect current page from URL
    detectCurrentPage() {
      const path = window.location.pathname;
      if (
        path.includes("home.html") ||
        path.endsWith("/user/") ||
        path.endsWith("/user")
      )
        return "home";
      if (path.includes("my-room.html")) return "my-room";
      if (path.includes("bills.html")) return "bills";
      if (path.includes("profile.html")) return "profile";
      if (path.includes("rooms.html")) return "rooms";
      return "home";
    },

    // Load user info into header
    loadUserInfo() {
      const user = Auth.getUser();
      if (!user) return;

      const displayName = user.fullname || user.name || user.username || "User";
      const email = user.email || "";
      const initial = displayName.charAt(0).toUpperCase();

      const userAvatar = document.getElementById("userAvatar");
      const userName = document.getElementById("userName");
      const dropdownName = document.getElementById("dropdownName");
      const dropdownEmail = document.getElementById("dropdownEmail");
      const welcomeName = document.getElementById("welcomeName");

      if (userAvatar) userAvatar.textContent = initial;
      if (userName) userName.textContent = displayName;
      if (dropdownName) dropdownName.textContent = displayName;
      if (dropdownEmail) dropdownEmail.textContent = email;
      if (welcomeName) welcomeName.textContent = displayName;
    },

    // Setup navigation active state
    setupNavigation() {
      // Desktop nav
      document.querySelectorAll(".nav-link[data-nav]").forEach((link) => {
        const navKey = link.getAttribute("data-nav");
        if (navKey === this.currentPage) {
          link.classList.add("active");
        } else {
          link.classList.remove("active");
        }
      });

      // Mobile nav
      document
        .querySelectorAll(".nav-link-mobile[data-nav]")
        .forEach((link) => {
          const navKey = link.getAttribute("data-nav");
          if (navKey === this.currentPage) {
            link.classList.add("active");
          } else {
            link.classList.remove("active");
          }
        });
    },

    // Setup user dropdown
    setupUserDropdown() {
      const btn = document.getElementById("userMenuBtn");
      const dropdown = document.getElementById("userDropdown");

      console.log("Layout: Setting up user dropdown", {
        btn: !!btn,
        dropdown: !!dropdown,
      });

      if (!btn || !dropdown) {
        console.warn("Layout: User dropdown elements not found");
        return;
      }

      // Remove old listeners by cloning
      const newBtn = btn.cloneNode(true);
      btn.parentNode.replaceChild(newBtn, btn);

      newBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log("Layout: User menu clicked");
        dropdown.classList.toggle("show");
        const notifDropdown = document.getElementById("notifDropdown");
        if (notifDropdown) notifDropdown.classList.remove("show");
      });

      document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target) && !newBtn.contains(e.target)) {
          dropdown.classList.remove("show");
        }
      });
    },

    // Setup notifications dropdown
    setupNotifications() {
      const bell = document.getElementById("notifBell");
      const dropdown = document.getElementById("notifDropdown");
      const badge = document.getElementById("notifBadge");
      const list = document.getElementById("notifList");

      console.log("Layout: Setting up notifications", {
        bell: !!bell,
        dropdown: !!dropdown,
      });

      if (!bell || !dropdown) {
        console.warn("Layout: Notification elements not found");
        return;
      }

      if (list) {
        list.innerHTML =
          '<div class="p-4 text-sm text-gray-500 text-center"><div class="animate-pulse">Đang tải thông báo...</div></div>';
      }

      // Load notifications from server
      this.loadNotifications();

      // Clone bell to remove old listeners
      const newBell = bell.cloneNode(true);
      bell.parentNode.replaceChild(newBell, bell);

      newBell.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log("Layout: Notification bell clicked");
        dropdown.classList.toggle("show");
        const userDropdown = document.getElementById("userDropdown");
        if (userDropdown) userDropdown.classList.remove("show");

        // Mark notifications as read when dropdown opens
        if (dropdown.classList.contains("show")) {
          this.markNotificationsAsRead();
        }
      });

      document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target) && !newBell.contains(e.target)) {
          dropdown.classList.remove("show");
        }
      });

      if (badge) badge.classList.add("hidden");
    },

    // Setup mobile menu
    setupMobileMenu() {
      const btn = document.getElementById("mobileMenuBtn");
      const nav = document.getElementById("mobileNav");
      if (!btn || !nav) return;

      btn.addEventListener("click", () => {
        nav.classList.toggle("hidden");
      });
    },

    // Setup logout
    setupLogout() {
      const logoutBtn = document.getElementById("logoutBtn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
          if (typeof Auth !== "undefined" && Auth.logout) {
            Auth.logout();
          } else {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            window.location.href = "/auth/login.html";
          }
        });
      }
    },

    // Update notification badge
    updateNotificationBadge(count) {
      const badge = document.getElementById("notifBadge");
      const status = document.getElementById("notifStatus");
      if (!badge) return;

      if (count > 0) {
        badge.textContent = count > 9 ? "9+" : count;
        badge.classList.remove("hidden");
        if (status) status.textContent = `${count} thông báo mới`;
      } else {
        badge.classList.add("hidden");
        if (status) status.textContent = "Chưa có thông báo";
      }
    },

    // Render notifications
    renderNotifications(notifications) {
      const list = document.getElementById("notifList");
      if (!list) return;

      if (!notifications || notifications.length === 0) {
        list.innerHTML =
          '<div class="p-4 text-sm text-gray-500 text-center">Chưa có thông báo mới</div>';
        this.updateNotificationBadge(0);
        return;
      }

      list.innerHTML = notifications
        .map(
          (item) => `
          <div class="px-4 py-3 flex items-start gap-3 hover:bg-gray-50 border-b border-gray-50 last:border-b-0 ${
            item.read ? "" : "bg-blue-50/50"
          }">
            <div class="mt-0.5 text-primary">
              <span class="material-symbols-outlined text-[18px]">${
                item.icon || "notifications"
              }</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold text-gray-900 truncate">${
                item.title || "Thông báo"
              }</div>
              <div class="text-sm text-gray-600 line-clamp-2">${
                item.message || ""
              }</div>
              ${
                item.time
                  ? `<div class="text-xs text-gray-400 mt-1">${item.time}</div>`
                  : ""
              }
            </div>
          </div>`
        )
        .join("");

      const unread = notifications.filter((n) => !n.read).length;
      this.updateNotificationBadge(unread);
    },

    // Set page title
    setPageTitle(title) {
      document.title = title ? `${title} - MotelHDK` : "MotelHDK";
    },

    // Load notifications from server
    async loadNotifications() {
      const list = document.getElementById("notifList");

      try {
        const token = localStorage.getItem("token");
        if (!token) return;

        const response = await fetch("/api/notifications", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to load notifications");
        }

        const data = await response.json();
        const notifications = data.notifications || [];

        // Transform notifications for rendering
        const formattedNotifications = notifications.map((n) => ({
          id: n._id || n.id,
          title: n.title || "Thông báo",
          message: n.message || "",
          read: n.status === "read",
          time: this.formatTimeAgo(n.created_at),
          icon: this.getNotificationIcon(n.type),
        }));

        this.renderNotifications(formattedNotifications);
      } catch (error) {
        console.error("Failed to load notifications:", error);
        if (list) {
          list.innerHTML =
            '<div class="p-4 text-sm text-gray-500 text-center">Chưa có thông báo mới</div>';
        }
        this.updateNotificationBadge(0);
      }
    },

    // Mark notifications as read
    async markNotificationsAsRead() {
      try {
        const token = localStorage.getItem("token");
        if (!token) return;

        await fetch("/api/notifications/read", {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        // Update badge
        this.updateNotificationBadge(0);

        // Update UI to show all as read
        const list = document.getElementById("notifList");
        if (list) {
          list.querySelectorAll(".bg-blue-50\\/50").forEach((el) => {
            el.classList.remove("bg-blue-50/50");
          });
        }
      } catch (error) {
        console.error("Failed to mark notifications as read:", error);
      }
    },

    // Get notification icon based on type
    getNotificationIcon(type) {
      const icons = {
        welcome: "celebration",
        reminder: "alarm",
        payment: "payments",
        warning: "warning",
        important: "priority_high",
        info: "info",
        system: "settings",
      };
      return icons[type] || "notifications";
    },

    // Format time ago
    formatTimeAgo(dateString) {
      if (!dateString) return "";

      const date = new Date(dateString);
      const now = new Date();
      const diff = Math.floor((now - date) / 1000);

      if (diff < 60) return "Vừa xong";
      if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
      if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`;
      if (diff < 604800) return `${Math.floor(diff / 86400)} ngày trước`;

      return date.toLocaleDateString("vi-VN");
    },
  };

  // Expose globally
  window.Layout = Layout;

  // Auto-init when DOM is ready
  function initLayout() {
    console.log("Layout: Initializing...");
    if (typeof Auth !== "undefined") {
      Layout.init();
      console.log("Layout: Initialized successfully");
    } else {
      console.error("Layout: Auth module not loaded");
    }
  }

  // Always wait for DOMContentLoaded to ensure all placeholders exist
  console.log("Layout: readyState =", document.readyState);
  if (document.readyState === "loading") {
    console.log("Layout: Waiting for DOMContentLoaded...");
    document.addEventListener("DOMContentLoaded", initLayout);
  } else {
    // DOM already loaded, init now
    console.log("Layout: DOM already ready, init now");
    initLayout();
  }
})();
