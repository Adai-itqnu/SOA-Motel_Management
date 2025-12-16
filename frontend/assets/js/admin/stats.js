/**
 * Admin Statistics Page JavaScript
 * Clean version - using TailwindCSS layout
 */

let revenueChart = null;
let roomStatusChart = null;
let revenueSourceChart = null;
let currentYear = new Date().getFullYear();
let isLoading = false;

document.addEventListener("DOMContentLoaded", function () {
  // Initialize admin layout (sidebar)
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  initYearSelect();
  loadAllStats();

  document.getElementById("yearSelect").addEventListener("change", function () {
    currentYear = parseInt(this.value);
    loadRevenueData();
  });
});

function initYearSelect() {
  const select = document.getElementById("yearSelect");
  if (!select) return;

  const startYear = 2023;
  const endYear = new Date().getFullYear() + 1;

  select.innerHTML = "";
  for (let year = endYear; year >= startYear; year--) {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = `Năm ${year}`;
    if (year === currentYear) option.selected = true;
    select.appendChild(option);
  }
}

async function loadAllStats() {
  if (isLoading) return;
  isLoading = true;
  showLoading(true);

  try {
    await Promise.all([loadOverviewStats(), loadRevenueData(), loadDebtData()]);
  } catch (error) {
    console.error("Error loading stats:", error);
  } finally {
    showLoading(false);
    isLoading = false;
  }
}

async function loadOverviewStats() {
  try {
    const response = await fetch("/api/reports/overview", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) throw new Error("Failed to load overview");

    const data = await response.json();

    // Room stats
    const rooms = data.rooms || {};
    setText("totalRooms", rooms.total || 0);
    setText("occupiedRooms", rooms.occupied || 0);
    setText("availableRooms", rooms.available || 0);

    const occupancyRate = rooms.occupancy_rate || 0;
    setText("occupancyRate", occupancyRate.toFixed(1));

    const occupancyBar = document.getElementById("occupancyBar");
    if (occupancyBar) occupancyBar.style.width = `${occupancyRate}%`;

    // Finance stats
    const finance = data.finance || {};
    setText("totalRevenue", formatCurrency(finance.total_revenue || 0));
    setText("totalDebt", formatCurrency(finance.total_debt || 0));
    setText("collectionRate", (finance.collection_rate || 0).toFixed(1));

    // Bills stats
    const bills = data.bills || {};
    setText("unpaidBills", (bills.unpaid || 0) + (bills.partial || 0));

    // Contracts
    setText("activeContracts", data.contracts?.active || 0);

    // Update room status chart
    updateRoomStatusChart(rooms);
  } catch (error) {
    console.error("Error loading overview:", error);
  }
}

async function loadRevenueData() {
  try {
    const response = await fetch(`/api/reports/revenue?year=${currentYear}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) throw new Error("Failed to load revenue");

    const data = await response.json();
    updateRevenueChart(data);
    updateRevenueSourceChart(data);
  } catch (error) {
    console.error("Error loading revenue:", error);
  }
}

async function loadDebtData() {
  try {
    const response = await fetch("/api/reports/debt", {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) throw new Error("Failed to load debt");

    const data = await response.json();
    updateDebtTable(data);
  } catch (error) {
    console.error("Error loading debt:", error);
  }
}

function updateRevenueChart(data) {
  const canvas = document.getElementById("revenueChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const monthlyData = data.monthly_data || [];

  const labels = monthlyData.map((m) => `T${m.month}`);
  const billsData = monthlyData.map((m) => m.bills_revenue || 0);
  const depositsData = monthlyData.map((m) => m.deposits_revenue || 0);

  // Destroy existing chart before creating new one
  if (revenueChart) {
    revenueChart.destroy();
    revenueChart = null;
  }

  revenueChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Doanh thu hóa đơn",
          data: billsData,
          backgroundColor: "rgba(99, 102, 241, 0.8)",
          borderColor: "#6366f1",
          borderWidth: 1,
        },
        {
          label: "Tiền cọc",
          data: depositsData,
          backgroundColor: "rgba(245, 158, 11, 0.8)",
          borderColor: "#f59e0b",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: (value) => formatCurrencyShort(value),
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: (context) =>
              `${context.dataset.label}: ${formatCurrency(context.raw)}`,
          },
        },
      },
    },
  });
}

function updateRoomStatusChart(rooms) {
  const canvas = document.getElementById("roomStatusChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  // Destroy existing chart before creating new one
  if (roomStatusChart) {
    roomStatusChart.destroy();
    roomStatusChart = null;
  }

  roomStatusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Đang thuê", "Còn trống", "Bảo trì"],
      datasets: [
        {
          data: [
            rooms.occupied || 0,
            rooms.available || 0,
            rooms.maintenance || 0,
          ],
          backgroundColor: ["#6366f1", "#10b981", "#6b7280"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            padding: 15,
            usePointStyle: true,
          },
        },
      },
      cutout: "65%",
    },
  });
}

function updateRevenueSourceChart(data) {
  const canvas = document.getElementById("revenueSourceChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const monthlyData = data.monthly_data || [];

  const totalBills = monthlyData.reduce(
    (sum, m) => sum + (m.bills_revenue || 0),
    0
  );
  const totalDeposits = monthlyData.reduce(
    (sum, m) => sum + (m.deposits_revenue || 0),
    0
  );

  setText("billsRevenue", formatCurrency(totalBills));
  setText("depositsRevenue", formatCurrency(totalDeposits));

  // Destroy existing chart before creating new one
  if (revenueSourceChart) {
    revenueSourceChart.destroy();
    revenueSourceChart = null;
  }

  revenueSourceChart = new Chart(ctx, {
    type: "pie",
    data: {
      labels: ["Hóa đơn", "Tiền cọc"],
      datasets: [
        {
          data: [totalBills, totalDeposits],
          backgroundColor: ["#6366f1", "#f59e0b"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => {
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage =
                total > 0 ? ((context.raw / total) * 100).toFixed(1) : 0;
              return `${context.label}: ${formatCurrency(
                context.raw
              )} (${percentage}%)`;
            },
          },
        },
      },
    },
  });
}

function updateDebtTable(data) {
  const table = document.getElementById("debtTable");
  if (!table) return;

  const tbody = table.querySelector("tbody");
  const details = data.details || [];

  // Sort by days overdue (descending)
  details.sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0));

  // Show top 10
  const topDebts = details.slice(0, 10);

  if (topDebts.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-4 py-8 text-center text-gray-400">
                    <svg class="w-12 h-12 mx-auto mb-2 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    Không có công nợ quá hạn
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = topDebts
    .map((bill) => {
      const daysOverdue = bill.days_overdue || 0;
      let statusBadge = "";

      if (daysOverdue > 30) {
        statusBadge =
          '<span class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs">Quá hạn lâu</span>';
      } else if (daysOverdue > 0) {
        statusBadge =
          '<span class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs">Quá hạn</span>';
      } else {
        statusBadge =
          '<span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">Chưa đến hạn</span>';
      }

      return `
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 font-medium text-indigo-600">${
                  bill.room_id || "-"
                }</td>
                <td class="px-4 py-3">
                    ${bill.tenant_name || "N/A"}
                    ${
                      bill.tenant_phone
                        ? `<br><span class="text-xs text-gray-400">${bill.tenant_phone}</span>`
                        : ""
                    }
                </td>
                <td class="px-4 py-3 text-red-600 font-semibold">${formatCurrency(
                  bill.debt_amount || 0
                )}</td>
                <td class="px-4 py-3">${
                  daysOverdue > 0 ? `${daysOverdue} ngày` : "-"
                }</td>
                <td class="px-4 py-3">${statusBadge}</td>
            </tr>
        `;
    })
    .join("");
}

// Helper functions
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatCurrency(amount) {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    minimumFractionDigits: 0,
  }).format(amount || 0);
}

function formatCurrencyShort(amount) {
  if (amount >= 1000000) {
    return (amount / 1000000).toFixed(1) + "M";
  } else if (amount >= 1000) {
    return (amount / 1000).toFixed(0) + "K";
  }
  return amount.toString();
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
