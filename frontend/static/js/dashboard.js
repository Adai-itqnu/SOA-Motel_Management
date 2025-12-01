(function () {
// Load dashboard stats
async function loadDashboardStats() {
  try {
    const headers = getAuthHeader();
    console.log("Dashboard: Making API calls with headers:", headers);

    const [roomsRes, tenantsRes, contractsRes, reportsRes] = await Promise.all([
      fetch(buildApiUrl("/api/rooms/stats"), { headers }),
      fetch(buildApiUrl("/api/tenants"), { headers }),
      fetch(buildApiUrl("/api/contracts?status=active"), { headers }),
      fetch(buildApiUrl("/api/reports/overview"), { headers }),
    ]);

    // Log response status
    console.log("Dashboard API responses:", {
      rooms: roomsRes.status,
      tenants: tenantsRes.status,
      contracts: contractsRes.status,
      reports: reportsRes.status,
    });

    // Room stats
    if (roomsRes.ok) {
      const roomStats = await roomsRes.json();
      const totalRoomsEl = document.getElementById("totalRooms");
      const availableRoomsEl = document.getElementById("availableRooms");
      const occupancyRateEl = document.getElementById("occupancyRate");

      if (totalRoomsEl) totalRoomsEl.textContent = roomStats.total || 0;
      if (availableRoomsEl)
        availableRoomsEl.textContent = roomStats.available || 0;
      if (occupancyRateEl)
        occupancyRateEl.textContent = (roomStats.occupancy_rate || 0) + "%";
    }

    // Tenant stats
    if (tenantsRes.ok) {
      const tenantsData = await tenantsRes.json();
      const totalTenantsEl = document.getElementById("totalTenants");
      if (totalTenantsEl) totalTenantsEl.textContent = tenantsData.total || 0;
    }

    // Contract stats
    if (contractsRes.ok) {
      const contractsData = await contractsRes.json();
      const activeContractsEl = document.getElementById("activeContracts");
      if (activeContractsEl)
        activeContractsEl.textContent = contractsData.total || 0;
    }

    // Revenue stats
    if (reportsRes.ok) {
      const reportsData = await reportsRes.json();
      if (reportsData && reportsData.finance) {
        const revenue = reportsData.finance.total_revenue || 0;
        const monthlyRevenueEl = document.getElementById("monthlyRevenue");
        if (monthlyRevenueEl)
          monthlyRevenueEl.textContent = formatPrice(revenue);
      }
    } else {
      console.error("Failed to load reports overview:", reportsRes.status);
    }

    // Load quick stats
    loadQuickStats();
  } catch (error) {
    console.error("Error loading dashboard stats:", error);
  }
}

// Load quick stats
async function loadQuickStats() {
  try {
    const headers = getAuthHeader();
    const [roomsRes, tenantsRes, contractsRes, reportsRes] = await Promise.all([
      fetch(buildApiUrl("/api/rooms/stats"), { headers }),
      fetch(buildApiUrl("/api/tenants"), { headers }),
      fetch(buildApiUrl("/api/contracts?status=active"), { headers }),
      fetch(buildApiUrl("/api/reports/overview"), { headers }),
    ]);

    const stats = [];

    if (roomsRes.ok) {
      const roomStats = await roomsRes.json();
      if (roomStats && typeof roomStats.total !== "undefined") {
        stats.push({
          icon: "🏠",
          title: `Tổng ${roomStats.total || 0} phòng`,
          desc: `${roomStats.available || 0} trống, ${
            roomStats.occupied || 0
          } đã cho thuê`,
        });
      }
    } else {
      console.error("Failed to load room stats:", roomsRes.status);
    }

    if (tenantsRes.ok) {
      const tenantsData = await tenantsRes.json();
      if (tenantsData && typeof tenantsData.total !== "undefined") {
        stats.push({
          icon: "👥",
          title: `${tenantsData.total || 0} người thuê`,
          desc: "Đang quản lý trong hệ thống",
        });
      }
    } else {
      console.error("Failed to load tenants:", tenantsRes.status);
    }

    if (contractsRes.ok) {
      const contractsData = await contractsRes.json();
      if (contractsData && typeof contractsData.total !== "undefined") {
        stats.push({
          icon: "📄",
          title: `${contractsData.total || 0} hợp đồng đang hoạt động`,
          desc: "Hợp đồng thuê phòng hiện tại",
        });
      }
    } else {
      console.error("Failed to load contracts:", contractsRes.status);
    }

    if (reportsRes.ok) {
      const reportsData = await reportsRes.json();
      if (reportsData && reportsData.finance) {
        const revenue = reportsData.finance.total_revenue || 0;
        const debt = reportsData.finance.total_debt || 0;
        stats.push({
          icon: "💰",
          title: `Doanh thu: ${formatPrice(revenue)}`,
          desc: `Còn nợ: ${formatPrice(debt)}`,
        });
      }
    } else {
      console.error("Failed to load reports:", reportsRes.status);
    }

    renderQuickStats(stats);
  } catch (error) {
    console.error("Error loading quick stats:", error);
    const quickStatsEl = document.getElementById("quickStats");
    if (quickStatsEl) {
      quickStatsEl.innerHTML =
        '<p style="color: #c62828;">❌ Không thể tải thống kê: ' +
        error.message +
        "</p>";
    }
  }
}

// Render quick stats
function renderQuickStats(stats) {
  const container = document.getElementById("quickStats");
  if (!container) return;

  if (stats.length === 0) {
    container.innerHTML =
      '<p style="text-align: center; color: #666;">Chưa có dữ liệu</p>';
    return;
  }

  container.innerHTML = stats
    .map(
      (stat) => `
        <div class="activity-item">
            <div class="activity-icon">${stat.icon}</div>
            <div class="activity-content">
                <div class="activity-title">${stat.title}</div>
                <div class="activity-time">${stat.desc}</div>
            </div>
        </div>
    `
    )
    .join("");
}
// Expose public API
window.loadDashboardStats = loadDashboardStats;

// Notify that tenants.js is ready
if (typeof window.scriptsLoaded === "undefined") {
  window.scriptsLoaded = {};
}
window.scriptsLoaded.dashboard = true;
console.log("dashboard.js loaded");
})();
