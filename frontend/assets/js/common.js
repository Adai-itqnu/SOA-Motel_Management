/**
 * Common Utilities & Config
 */
// Always use relative `/api`.
// - When browsing through the gateway (:80), this hits the gateway directly.
// - When browsing the frontend container (:3000), frontend nginx proxies `/api/*` to the gateway.
const API_URL = "/api";

// Storage helpers
const Storage = {
  get: (key) => localStorage.getItem(key),
  set: (key, value) => localStorage.setItem(key, value),
  remove: (key) => localStorage.removeItem(key),
  getJSON: (key) => {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : null;
    } catch {
      return null;
    }
  },
  setJSON: (key, value) => localStorage.setItem(key, JSON.stringify(value)),
  clear: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },
};

// Auth helpers
const Auth = {
  getToken: () => Storage.get("token"),
  setToken: (token) => Storage.set("token", token),
  getUser: () => Storage.getJSON("user") || {},
  setUser: (user) => Storage.setJSON("user", user),
  isLoggedIn: () => {
    const token = Storage.get("token");
    const user = Storage.getJSON("user");
    return !!(token && user && user.role);
  },

  logout: () => {
    Storage.clear();
    window.location.href = "/auth/login.html";
  },

  // Check authentication - runs on page load for protected pages
  checkAuth: (requiredRole = null) => {
    const currentPath = window.location.pathname;

    // Don't check on auth pages
    if (currentPath.includes("/auth/")) {
      return true;
    }

    const token = Auth.getToken();
    const user = Auth.getUser();

    // No token or user - redirect to login
    if (!token || !user || !user.role) {
      console.warn("No valid session found, redirecting to login");
      Storage.clear();
      window.location.href = "/auth/login.html";
      return false;
    }

    // Check role if required
    if (requiredRole && user.role !== requiredRole) {
      console.warn(`Required role: ${requiredRole}, got: ${user.role}`);
      Storage.clear();
      window.location.href = "/auth/login.html";
      return false;
    }

    // Verify token with server (async, won't block page load)
    Auth.verifyToken();

    return true;
  },

  // Verify token with server
  verifyToken: async () => {
    try {
      const response = await fetch(`${API_URL}/auth/verify`, {
        headers: { Authorization: `Bearer ${Auth.getToken()}` },
      });

      if (!response.ok) {
        console.warn("Token verification failed, logging out");
        Storage.clear();
        window.location.href = "/auth/login.html";
        return false;
      }
      return true;
    } catch (error) {
      console.error("Token verification error:", error);
      // Don't logout on network errors - might just be connectivity issue
      return true;
    }
  },

  // Redirect based on user role
  redirectByRole: () => {
    const user = Auth.getUser();
    if (user.role === "admin") {
      window.location.href = "/admin/dashboard.html";
    } else {
      window.location.href = "/user/home.html";
    }
  },
};

// Legacy/global helpers for inline onclick handlers in HTML
function logout() {
  Auth.logout();
}

// API helpers
const API = {
  headers: (includeAuth = true) => {
    const headers = { "Content-Type": "application/json" };
    if (includeAuth && Auth.getToken()) {
      headers["Authorization"] = `Bearer ${Auth.getToken()}`;
    }
    return headers;
  },

  handleResponse: async (response) => {
    try {
      const data = await response.json();

      // Handle 401 Unauthorized - token expired or invalid
      if (response.status === 401) {
        console.warn("Unauthorized response, logging out");
        Storage.clear();
        window.location.href = "/auth/login.html";
        return { ok: false, data: { message: "Phiên đăng nhập hết hạn" } };
      }

      return { ok: response.ok, data, status: response.status };
    } catch (error) {
      return {
        ok: false,
        data: { message: "Lỗi xử lý response" },
        status: response.status,
      };
    }
  },

  get: async (endpoint) => {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        headers: API.headers(),
      });
      return API.handleResponse(response);
    } catch (error) {
      console.error("API GET error:", error);
      return { ok: false, data: { message: "Lỗi kết nối server" } };
    }
  },

  post: async (endpoint, body) => {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: API.headers(),
        body: JSON.stringify(body),
      });
      return API.handleResponse(response);
    } catch (error) {
      console.error("API POST error:", error);
      return { ok: false, data: { message: "Lỗi kết nối server" } };
    }
  },

  put: async (endpoint, body) => {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "PUT",
        headers: API.headers(),
        body: JSON.stringify(body),
      });
      return API.handleResponse(response);
    } catch (error) {
      console.error("API PUT error:", error);
      return { ok: false, data: { message: "Lỗi kết nối server" } };
    }
  },

  delete: async (endpoint) => {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "DELETE",
        headers: API.headers(),
      });
      return API.handleResponse(response);
    } catch (error) {
      console.error("API DELETE error:", error);
      return { ok: false, data: { message: "Lỗi kết nối server" } };
    }
  },
};

// UI Helpers
const UI = {
  show: (id) => document.getElementById(id)?.classList.remove("hidden"),
  hide: (id) => document.getElementById(id)?.classList.add("hidden"),
  toggle: (id) => document.getElementById(id)?.classList.toggle("hidden"),
  setText: (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  },
  setHTML: (id, html) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  },
  getValue: (id) => document.getElementById(id)?.value?.trim() || "",

  showError: (containerId, message) => {
    const container = document.getElementById(containerId);
    if (container) {
      container.classList.remove("hidden");
      const textEl = container.querySelector("span") || container;
      textEl.textContent = message;
    }
  },

  hideError: (containerId) => {
    document.getElementById(containerId)?.classList.add("hidden");
  },

  formatCurrency: (amount) => {
    return new Intl.NumberFormat("vi-VN").format(amount || 0) + " VNĐ";
  },
};

// Validation helpers
const Validate = {
  email: (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email),
  phone: (phone) => /^[0-9]{10,11}$/.test(phone.replace(/[\s-]/g, "")),
  required: (value) => value && value.trim().length > 0,
  minLength: (value, min) => value && value.length >= min,
};

// Debug helper
console.log(
  "Common.js loaded. Auth status:",
  Auth.isLoggedIn() ? "Logged in" : "Not logged in"
);
