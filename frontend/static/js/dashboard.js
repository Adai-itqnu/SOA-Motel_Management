// Load dashboard stats
async function loadDashboardStats() {
  try {
    const headers = getAuthHeader();
    console.log("Dashboard: Making API calls with headers:", headers);

    const [roomsRes, tenantsRes, contractsRes, reportsRes] = await Promise.all([
      fetch("/api/rooms/stats", { headers }),
      fetch("/api/tenants", { headers }),
      fetch("/api/contracts?status=active", { headers }),
      fetch("/api/reports/overview", { headers }),
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
      const revenue = reportsData.finance?.total_revenue || 0;
      const monthlyRevenueEl = document.getElementById("monthlyRevenue");
      if (monthlyRevenueEl) monthlyRevenueEl.textContent = formatPrice(revenue);
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
    const [roomsRes, tenantsRes, contractsRes, reportsRes] = await Promise.all([
      fetch("/api/rooms/stats", { headers: getAuthHeader() }),
      fetch("/api/tenants", { headers: getAuthHeader() }),
      fetch("/api/contracts?status=active", { headers: getAuthHeader() }),
      fetch("/api/reports/overview", { headers: getAuthHeader() }),
    ]);

    const stats = [];

    if (roomsRes.ok) {
      const roomStats = await roomsRes.json();
      stats.push({
        icon: "🏠",
        title: `Tổng ${roomStats.total} phòng`,
        desc: `${roomStats.available} trống, ${roomStats.occupied} đã cho thuê`,
      });
    }

    if (tenantsRes.ok) {
      const tenantsData = await tenantsRes.json();
      stats.push({
        icon: "👥",
        title: `${tenantsData.total} người thuê`,
        desc: "Đang quản lý trong hệ thống",
      });
    }

    if (contractsRes.ok) {
      const contractsData = await contractsRes.json();
      stats.push({
        icon: "📄",
        title: `${contractsData.total} hợp đồng đang hoạt động`,
        desc: "Hợp đồng thuê phòng hiện tại",
      });
    }

    if (reportsRes.ok) {
      const reportsData = await reportsRes.json();
      const revenue = reportsData.finance?.total_revenue || 0;
      const debt = reportsData.finance?.total_debt || 0;
      stats.push({
        icon: "💰",
        title: `Doanh thu: ${formatPrice(revenue)}`,
        desc: `Còn nợ: ${formatPrice(debt)}`,
      });
    }

    renderQuickStats(stats);
  } catch (error) {
    console.error("Error loading quick stats:", error);
    const quickStatsEl = document.getElementById("quickStats");
    if (quickStatsEl) {
      quickStatsEl.innerHTML =
        '<p style="color: #c62828;">❌ Không thể tải thống kê</p>';
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
