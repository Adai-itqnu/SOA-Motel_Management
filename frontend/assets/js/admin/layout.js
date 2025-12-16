/**
 * Admin Layout Component
 * Injects shared sidebar and header into admin pages
 */

const AdminLayout = {
  // Layout fragment served by nginx as a static file
  layoutUrl: "/admin/layout.html",

  // Menu items configuration (fallback if layout.html can't be loaded)
  menuItems: [
    { href: "/admin/dashboard.html", icon: "home", label: "Dashboard" },
    { href: "/admin/rooms.html", icon: "room", label: "Quản lý phòng" },
    { href: "/admin/users.html", icon: "users", label: "Người dùng" },
    { href: "/admin/bookings.html", icon: "calendar", label: "Đặt phòng" },
    { href: "/admin/contracts.html", icon: "document", label: "Hợp đồng" },
    { href: "/admin/bills.html", icon: "money", label: "Hóa đơn" },
    {
      href: "/admin/payments.html",
      icon: "chart",
      label: "Lịch sử thanh toán",
    },
  ],

  // SVG Icons
  icons: {
    home: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>',
    room: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>',
    users:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>',
    document:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>',
    calendar:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>',
    money:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"></path>',
    chart:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>',
    logout:
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>',
  },

  // Get current page path
  getCurrentPath() {
    return window.location.pathname;
  },

  // Check if menu item is active
  isActive(href) {
    return this.getCurrentPath().includes(href.replace("/admin/", ""));
  },

  getSidebarContainer() {
    return (
      document.getElementById("sidebarContainer") ||
      document.getElementById("sidebar-container") ||
      document.getElementById("sidebar-container")
    );
  },

  ensureSidebarContainer() {
    let sidebarContainer =
      document.getElementById("sidebarContainer") ||
      document.getElementById("sidebar-container");

    if (!sidebarContainer) {
      sidebarContainer = document.createElement("div");
      sidebarContainer.id = "sidebarContainer";
      document.body.insertBefore(sidebarContainer, document.body.firstChild);
    } else if (sidebarContainer.id !== "sidebarContainer") {
      sidebarContainer.id = "sidebarContainer";
    }

    return sidebarContainer;
  },

  applyUserInfo() {
    const user = Auth.getUser() || {};
    const userName = user.fullname || user.name || user.username || "Admin";

    const nameEl = document.getElementById("adminUserName");
    if (nameEl) nameEl.textContent = userName;

    const initialEl = document.getElementById("adminUserInitial");
    if (initialEl) initialEl.textContent = userName.charAt(0).toUpperCase();
  },

  applyActiveNav() {
    const currentPath = window.location.pathname;
    const links = document.querySelectorAll("a[data-admin-nav]");

    links.forEach((link) => {
      // Reset base state
      link.classList.remove("sidebar-active", "text-white");
      if (!link.classList.contains("text-gray-300")) {
        link.classList.add("text-gray-300");
      }

      // Active match
      if (link.getAttribute("href") === currentPath) {
        link.classList.add("sidebar-active", "text-white");
        link.classList.remove("text-gray-300");
      }
    });
  },

  wireLogout() {
    const btn = document.getElementById("adminLogoutBtn");
    if (!btn) return;

    btn.addEventListener("click", () => {
      this.logout();
    });
  },

  loadLayoutInto(container) {
    // Load HTML fragment (sidebar) from a static file
    fetch(this.layoutUrl, { cache: "no-cache" })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load layout: ${res.status}`);
        return res.text();
      })
      .then((html) => {
        container.innerHTML = html;
        this.applyUserInfo();
        this.applyActiveNav();
        this.wireLogout();
      })
      .catch(() => {
        // Fallback: keep old JS-generated sidebar
        container.innerHTML = this.generateSidebar();
      });
  },

  // Generate sidebar HTML
  generateSidebar() {
    const user = Auth.getUser() || {};
    const userName = user.fullname || user.name || user.username || "Admin";

    const menuHTML = this.menuItems
      .map((item) => {
        const isActive = this.isActive(item.href);
        const activeClass = isActive
          ? "sidebar-active text-white"
          : "text-gray-300 hover:text-white hover:bg-white/5";

        return `
                <a href="${
                  item.href
                }" class="flex items-center gap-3 px-4 py-3 rounded-xl ${activeClass} transition-all">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        ${this.icons[item.icon]}
                    </svg>
                    <span>${item.label}</span>
                </a>
            `;
      })
      .join("");

    return `
            <aside id="adminSidebar" class="fixed left-0 top-0 w-64 h-full bg-sidebar text-white z-50">
                <!-- Logo -->
                <div class="p-6 border-b border-white/10">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                ${this.icons.room}
                            </svg>
                        </div>
                        <div>
                            <h1 class="font-bold text-lg">Motel Admin</h1>
                            <p class="text-xs text-gray-400">Quản lý nhà trọ</p>
                        </div>
                    </div>
                </div>

                <!-- Navigation -->
                <nav class="p-4 space-y-2">
                    ${menuHTML}
                </nav>

                <!-- User & Logout -->
                <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-white/10">
                    <div class="flex items-center gap-3 mb-3 px-2">
                        <div class="w-8 h-8 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white text-sm font-bold">
                            ${userName.charAt(0).toUpperCase()}
                        </div>
                        <span class="text-sm text-gray-300">${userName}</span>
                    </div>
                    <button onclick="AdminLayout.logout()" class="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition-all">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            ${this.icons.logout}
                        </svg>
                        <span>Đăng xuất</span>
                    </button>
                </div>
            </aside>
        `;
  },

  // Generate styles
  generateStyles() {
    return `
            <style>
                .sidebar-active { 
                    background: rgba(255,255,255,0.1); 
                    border-left: 3px solid #8b5cf6; 
                }
                .bg-sidebar { 
                    background-color: #1e1b4b; 
                }
                .modal { display: none; }
                .modal.active { display: flex; }
                .card-hover:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
                }
            </style>
        `;
  },

  // Initialize layout
  init() {
    // Check auth first
    if (!Auth.checkAuth("admin")) {
      return;
    }

    // Ensure sidebar container exists (normalize id across pages)
    const sidebarContainer = this.ensureSidebarContainer();

    // Prefer HTML layout fragment, fallback to JS template
    this.loadLayoutInto(sidebarContainer);

    // Ensure main content has left margin
    const main = document.querySelector("main");
    if (main && !main.classList.contains("ml-64")) {
      main.classList.add("ml-64");
    }
  },

  // Logout function
  logout() {
    Auth.logout();
  },
};

// Don't auto-init - let each page control when to init
// This prevents double auth check issues
