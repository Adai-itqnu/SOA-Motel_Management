// Authentication
function checkAuth() {
  const token = localStorage.getItem("token");
  const user = JSON.parse(localStorage.getItem("user") || "{}");

  if (!token || user.role !== "admin") {
    window.location.href = "/login";
    return false;
  }

  // Set user info in header
  const userNameEl = document.getElementById("userName");
  if (userNameEl) {
    userNameEl.textContent = user.name || user.username;
  }

  return true;
}

// Get auth header for API calls
function getAuthHeader() {
  const token = localStorage.getItem("token");
  if (!token) {
    console.error("Token không tồn tại trong localStorage");
    // Redirect to login if no token (only if not already on login page)
    if (
      window.location.pathname !== "/login" &&
      window.location.pathname !== "/register"
    ) {
      console.log("Redirecting to login...");
      window.location.href = "/login";
    }
    return {
      "Content-Type": "application/json",
    };
  }

  // Debug: log token (first 20 chars only for security)
  console.log("Using token:", token.substring(0, 20) + "...");

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

// Expose getAuthHeader to window
window.getAuthHeader = getAuthHeader;

// Logout
window.logout = function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  window.location.href = "/login";
};

// Format price
function formatPrice(price) {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(price);
}

// Format date
function formatDate(dateString) {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return date.toLocaleDateString("vi-VN");
}

// Expose utility functions to window
window.formatPrice = formatPrice;
window.formatDate = formatDate;

// Navigation
window.navigateToSection = function navigateToSection(section) {
  console.log("navigateToSection called with section:", section);
  // Remove active class from all menu items
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.classList.remove("active");
  });

  // Add active class to clicked menu item
  const menuItem = document.querySelector(`[data-section="${section}"]`);
  if (menuItem) {
    menuItem.classList.add("active");
  }

  // Hide all content panels
  document.querySelectorAll(".content-panel").forEach((panel) => {
    panel.classList.remove("active");
  });

  // Show selected content panel
  const contentPanel = document.getElementById(`${section}Panel`);
  if (contentPanel) {
    console.log(`Showing panel: ${section}Panel`);
    contentPanel.classList.add("active");
  } else {
    console.error(`Panel not found: ${section}Panel`);
  }

  // Load section data
  loadSectionData(section);
};

// Wait for a function to be available (with timeout)
function waitForFunction(functionName, timeout = 5000, interval = 50) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    const checkFunction = () => {
      if (typeof window[functionName] === "function") {
        resolve(window[functionName]);
      } else if (Date.now() - startTime >= timeout) {
        reject(new Error(`Function ${functionName} not available after ${timeout}ms`));
      } else {
        setTimeout(checkFunction, interval);
      }
    };
    checkFunction();
  });
}

// Wait for tenants.js to be ready
async function waitForTenants() {
  try {
    await waitForFunction("initializeTenantsHandlers", 3000);
    await waitForFunction("loadTenantsData", 3000);
    await waitForFunction("switchTenantTab", 3000);
    return true;
  } catch (error) {
    console.error("Error waiting for tenants functions:", error);
    return false;
  }
}

// Wait for rooms.js to be ready
async function waitForRooms() {
  try {
    await waitForFunction("loadRoomsData", 3000);
    return true;
  } catch (error) {
    console.error("Error waiting for rooms functions:", error);
    return false;
  }
}

// Wait for dashboard.js to be ready
async function waitForDashboard() {
  try {
    await waitForFunction("loadDashboardStats", 3000);
    return true;
  } catch (error) {
    console.error("Error waiting for dashboard functions:", error);
    return false;
  }
}

// Wait for reports.js to be ready
async function waitForReports() {
  try {
    await waitForFunction("loadReportsData", 3000);
    return true;
  } catch (error) {
    console.error("Error waiting for reports functions:", error);
    return false;
  }
}

// Load section data with proper waiting
function loadSectionData(section) {
  switch (section) {
    case "dashboard":
      if (typeof loadDashboardStats === "function") {
        loadDashboardStats();
      }
      break;
    case "rooms":
      if (typeof loadRoomsData === "function") {
        loadRoomsData();
      }
      break;
    case "tenants":
      console.log("Loading tenants section...");
      if (typeof loadTenantsData === "function") {
        loadTenantsData();
      }
      break;
    case "contracts":
      console.log("Loading contracts section...");
      if (typeof loadContractsData === "function") {
        loadContractsData();
      }
      break;
    case "bookings":
      console.log("Loading bookings section...");
      if (typeof loadBookingsData === "function") {
        loadBookingsData();
      }
      break;
    case "reports":
      if (typeof loadReportsData === "function") {
        loadReportsData();
      }
      break;
  }
}

// Expose initialization function
window.initializeAdmin = function() {
  if (!checkAuth()) return;
  
  // Set default section
  const defaultSection = "dashboard";
  navigateToSection(defaultSection);

  // Add click handlers to menu items
  document.querySelectorAll(".menu-item").forEach((item) => {
    item.addEventListener("click", function () {
      const section = this.getAttribute("data-section");
      if (section) {
        navigateToSection(section);
      }
    });
  });
};
