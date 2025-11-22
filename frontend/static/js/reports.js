// Switch report tab
window.switchReportTab = function switchReportTab(tab) {
  document
    .querySelectorAll("#reportsPanel .tab")
    .forEach((t) => t.classList.remove("active"));

  const overviewTab = document.getElementById("overviewTabContent");
  const revenueTab = document.getElementById("revenueTabContent");
  const roomsTab = document.getElementById("roomsTabContent");
  const popularRoomsSection = document.getElementById("popularRoomsSection");
  const debtTab = document.getElementById("debtTabContent");

  // Hide all tabs
  if (overviewTab) overviewTab.style.display = "none";
  if (revenueTab) revenueTab.style.display = "none";
  if (roomsTab) roomsTab.style.display = "none";
  if (popularRoomsSection) popularRoomsSection.style.display = "none";
  if (debtTab) debtTab.style.display = "none";

  const tabs = document.querySelectorAll("#reportsPanel .tab");

  if (tab === "overview") {
    tabs[0].classList.add("active");
    if (overviewTab) overviewTab.style.display = "block";
    loadOverview();
  } else if (tab === "revenue") {
    tabs[1].classList.add("active");
    if (revenueTab) revenueTab.style.display = "block";
    loadRevenueReport();
  } else if (tab === "rooms") {
    tabs[2].classList.add("active");
    if (roomsTab) roomsTab.style.display = "block";
    if (popularRoomsSection) popularRoomsSection.style.display = "block";
    loadRoomStatistics();
  } else if (tab === "debt") {
    tabs[3].classList.add("active");
    if (debtTab) debtTab.style.display = "block";
    loadDebtReport();
  }
};

// Load reports data
window.loadReportsData = async function loadReportsData() {
  loadOverview();
};

// Load overview
async function loadOverview() {
  try {
    const response = await fetch("/api/reports/overview", {
      headers: getAuthHeader(),
    });
    if (!response.ok) throw new Error("Không thể tải dữ liệu tổng quan");
    const data = await response.json();

    const overviewTotalRooms = document.getElementById("overviewTotalRooms");
    const overviewOccupiedRooms = document.getElementById(
      "overviewOccupiedRooms"
    );
    const overviewActiveContracts = document.getElementById(
      "overviewActiveContracts"
    );
    const overviewTotalRevenue = document.getElementById(
      "overviewTotalRevenue"
    );
    const overviewTotalDebt = document.getElementById("overviewTotalDebt");
    const overviewCollectionRate = document.getElementById(
      "overviewCollectionRate"
    );

    if (overviewTotalRooms)
      overviewTotalRooms.textContent = data.rooms?.total || 0;
    if (overviewOccupiedRooms)
      overviewOccupiedRooms.textContent = data.rooms?.occupied || 0;
    if (overviewActiveContracts)
      overviewActiveContracts.textContent = data.contracts?.active || 0;
    if (overviewTotalRevenue)
      overviewTotalRevenue.textContent = formatPrice(
        data.finance?.total_revenue || 0
      );
    if (overviewTotalDebt)
      overviewTotalDebt.textContent = formatPrice(
        data.finance?.total_debt || 0
      );
    if (overviewCollectionRate)
      overviewCollectionRate.textContent =
        (data.finance?.collection_rate || 0) + "%";
  } catch (error) {
    console.error("Error loading overview:", error);
  }
}

// Load revenue report
window.loadRevenueReport = async function loadRevenueReport() {
  const revenueYear = document.getElementById("revenueYear");
  const year = revenueYear
    ? revenueYear.value || new Date().getFullYear()
    : new Date().getFullYear();
  const content = document.getElementById("revenueContent");

  if (!content) return;

  content.innerHTML =
    '<div class="loading"><div class="spinner"></div><p>Đang tải dữ liệu...</p></div>';

  try {
    const response = await fetch(`/api/reports/revenue?year=${year}`, {
      headers: getAuthHeader(),
    });
    if (!response.ok) throw new Error("Không thể tải báo cáo doanh thu");
    const data = await response.json();

    const maxRevenue = Math.max(...data.monthly_data.map((m) => m.revenue), 1);
    const chartHeight = 250;

    content.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h3>Doanh thu năm ${data.year}</h3>
        <p style="color: #666; margin-top: 5px;">Tổng doanh thu: <strong>${formatPrice(
          data.total_revenue
        )}</strong></p>
      </div>
      <div class="chart-container">
        <div class="bar-chart">
          ${data.monthly_data
            .map((month) => {
              const height = (month.revenue / maxRevenue) * chartHeight;
              return `
                <div class="bar-item">
                  <div class="bar" style="height: ${height}px;">
                    <div class="bar-value">${formatPrice(month.revenue)}</div>
                  </div>
                  <div class="bar-label">Tháng ${month.month}</div>
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
      <table style="margin-top: 30px;">
        <thead>
          <tr>
            <th>Tháng</th>
            <th>Doanh thu</th>
            <th>Số hóa đơn</th>
          </tr>
        </thead>
        <tbody>
          ${data.monthly_data
            .map(
              (month) => `
            <tr>
              <td>Tháng ${month.month}</td>
              <td>${formatPrice(month.revenue)}</td>
              <td>${month.bills_count}</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (error) {
    content.innerHTML = `<p style="color: #c62828;">❌ ${error.message}</p>`;
  }
};

// Load room statistics
async function loadRoomStatistics() {
  const popularityContent = document.getElementById("roomPopularityContent");
  const popularRoomsBody = document.getElementById("popularRoomsTableBody");

  if (popularityContent) {
    popularityContent.innerHTML =
      '<div class="loading"><div class="spinner"></div><p>Đang tải dữ liệu...</p></div>';
  }
  if (popularRoomsBody) {
    popularRoomsBody.innerHTML =
      '<tr><td colspan="6" style="text-align: center;">Đang tải...</td></tr>';
  }

  try {
    // Load rooms
    const roomsRes = await fetch("/api/rooms", {
      headers: getAuthHeader(),
    });
    if (!roomsRes.ok) throw new Error("Không thể tải danh sách phòng");
    const roomsData = await roomsRes.json();

    // Load contracts
    const contractsRes = await fetch("/api/contracts", {
      headers: getAuthHeader(),
    });
    if (!contractsRes.ok) throw new Error("Không thể tải danh sách hợp đồng");
    const contractsData = await contractsRes.json();

    // Calculate room popularity
    const roomStats = {};
    roomsData.rooms.forEach((room) => {
      roomStats[room._id] = {
        room: room,
        contractCount: 0,
        totalRevenue: 0,
        totalDays: 0,
      };
    });

    contractsData.contracts.forEach((contract) => {
      if (roomStats[contract.room_id]) {
        roomStats[contract.room_id].contractCount++;
        roomStats[contract.room_id].totalRevenue += contract.monthly_rent || 0;
        if (contract.start_date && contract.end_date) {
          const start = new Date(contract.start_date);
          const end = new Date(contract.end_date);
          const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
          roomStats[contract.room_id].totalDays += days;
        }
      }
    });

    // Sort by contract count
    const sortedRooms = Object.values(roomStats)
      .sort((a, b) => b.contractCount - a.contractCount)
      .slice(0, 10);

    // Render popularity cards
    if (popularityContent) {
      popularityContent.innerHTML = `
        <div class="room-popularity">
          ${sortedRooms
            .map(
              (stat, index) => `
            <div class="popularity-card">
              <div class="popularity-rank">#${index + 1}</div>
              <div class="popularity-room">${stat.room.name}</div>
              <div class="popularity-stats">
                Số lần thuê: ${stat.contractCount} | 
                Doanh thu: ${formatPrice(stat.totalRevenue)}
              </div>
            </div>
          `
            )
            .join("")}
        </div>
      `;
    }

    // Render popular rooms table
    if (popularRoomsBody) {
      popularRoomsBody.innerHTML = sortedRooms
        .map((stat, index) => {
          const occupancyRate =
            stat.room.status === "occupied"
              ? 100
              : stat.contractCount > 0
              ? Math.min(100, (stat.totalDays / 365) * 100)
              : 0;
          return `
          <tr>
            <td><strong>#${index + 1}</strong></td>
            <td>${stat.room._id}</td>
            <td><strong>${stat.room.name}</strong></td>
            <td>${stat.contractCount}</td>
            <td>${formatPrice(stat.totalRevenue)}</td>
            <td>${occupancyRate.toFixed(1)}%</td>
          </tr>
        `;
        })
        .join("");
    }
  } catch (error) {
    if (popularityContent) {
      popularityContent.innerHTML = `<p style="color: #c62828;">❌ ${error.message}</p>`;
    }
    if (popularRoomsBody) {
      popularRoomsBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #c62828;">${error.message}</td></tr>`;
    }
  }
}

// Load debt report
async function loadDebtReport() {
  const content = document.getElementById("debtContent");
  if (!content) return;

  content.innerHTML =
    '<div class="loading"><div class="spinner"></div><p>Đang tải dữ liệu...</p></div>';

  try {
    const response = await fetch("/api/reports/debt", {
      headers: getAuthHeader(),
    });
    if (!response.ok) throw new Error("Không thể tải báo cáo công nợ");
    const data = await response.json();

    content.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h3>Tổng quan công nợ</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px;">
          <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
            <div style="font-size: 24px; font-weight: 700; color: #c62828;">${formatPrice(
              data.total_debt
            )}</div>
            <div style="color: #666; font-size: 14px;">Tổng công nợ</div>
          </div>
          <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
            <div style="font-size: 24px; font-weight: 700; color: #333;">${
              data.total_bills
            }</div>
            <div style="color: #666; font-size: 14px;">Số hóa đơn nợ</div>
          </div>
          <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
            <div style="font-size: 24px; font-weight: 700; color: #f57c00;">${
              data.overdue_bills
            }</div>
            <div style="color: #666; font-size: 14px;">Hóa đơn quá hạn</div>
          </div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Mã hóa đơn</th>
            <th>Người thuê</th>
            <th>Phòng</th>
            <th>Tổng tiền</th>
            <th>Đã thanh toán</th>
            <th>Còn nợ</th>
            <th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          ${data.details
            .map(
              (bill) => `
            <tr>
              <td>${bill._id}</td>
              <td>${bill.tenant_name || "-"}</td>
              <td>${bill.room_id}</td>
              <td>${formatPrice(bill.total_amount)}</td>
              <td>${formatPrice(bill.paid_amount)}</td>
              <td><strong>${formatPrice(bill.debt_amount)}</strong></td>
              <td>${
                bill.status === "unpaid"
                  ? "Chưa thanh toán"
                  : "Thanh toán một phần"
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (error) {
    content.innerHTML = `<p style="color: #c62828;">❌ ${error.message}</p>`;
  }
}

// Initialize year selector
document.addEventListener("DOMContentLoaded", function () {
  const currentYear = new Date().getFullYear();
  const yearSelect = document.getElementById("revenueYear");
  if (yearSelect) {
    for (let i = currentYear; i >= currentYear - 5; i--) {
      const option = document.createElement("option");
      option.value = i;
      option.textContent = i;
      if (i === currentYear) option.selected = true;
      yearSelect.appendChild(option);
    }
  }
});
