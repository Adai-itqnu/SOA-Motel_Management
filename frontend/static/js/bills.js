(function () {
let allBills = [];
let allTenants = [];
let allRooms = [];
let currentEditId = null;

// Format price
function formatPrice(price) {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(price);
}

// Load bills data
window.loadBillsData = async function loadBillsData() {
  try {
    const headers = getAuthHeader();
    const response = await fetch(buildApiUrl("/api/bills"), {
      headers,
    });
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách hóa đơn");
    const data = await response.json();
    allBills = data.bills || [];
    filterBills();
    await loadTenantsAndRooms();
  } catch (error) {
    console.error("Error loading bills:", error);
  }
};

// Load tenants and rooms for dropdowns
async function loadTenantsAndRooms() {
  try {
    const headers = getAuthHeader();
    
    // Load tenants
    const tenantsResponse = await fetch(buildApiUrl("/api/tenants"), { headers });
    if (tenantsResponse.ok) {
      const tenantsData = await tenantsResponse.json();
      allTenants = tenantsData.tenants || [];
    }
    
    // Load rooms
    const roomsResponse = await fetch(buildApiUrl("/api/rooms"), { headers });
    if (roomsResponse.ok) {
      const roomsData = await roomsResponse.json();
      allRooms = roomsData.rooms || [];
    }
    
    // Populate dropdowns
    populateTenantDropdown();
    populateRoomDropdown();
  } catch (error) {
    console.error("Error loading tenants/rooms:", error);
  }
}

// Populate tenant dropdown
function populateTenantDropdown() {
  const select = document.getElementById("billTenantId");
  if (!select) return;
  
  select.innerHTML = '<option value="">Chọn người thuê</option>';
  allTenants.forEach((tenant) => {
    const option = document.createElement("option");
    option.value = tenant._id || tenant.id;
    option.textContent = `${tenant.name} (${tenant.phone || ""})`;
    select.appendChild(option);
  });
}

// Populate room dropdown
function populateRoomDropdown() {
  const select = document.getElementById("billRoomId");
  if (!select) return;
  
  select.innerHTML = '<option value="">Chọn phòng</option>';
  allRooms.forEach((room) => {
    const option = document.createElement("option");
    option.value = room._id || room.id;
    option.textContent = `${room.name} - ${formatPrice(room.price)}`;
    select.appendChild(option);
  });
}

// Filter bills
function filterBills() {
  const searchInput = document.getElementById("billSearchInput");
  const statusFilter = document.getElementById("billStatusFilter");
  const monthFilter = document.getElementById("billMonthFilter");

  if (!searchInput || !statusFilter) return;

  const searchText = searchInput.value.toLowerCase();
  const statusFilterValue = statusFilter.value;
  const monthFilterValue = monthFilter ? monthFilter.value : "";

  let filtered = allBills.filter((bill) => {
    const matchSearch = 
      (bill._id || bill.id || "").toLowerCase().includes(searchText) ||
      (bill.tenant_id || "").toLowerCase().includes(searchText);
    const matchStatus = !statusFilterValue || bill.status === statusFilterValue;
    const matchMonth = !monthFilterValue || bill.month === monthFilterValue;
    return matchSearch && matchStatus && matchMonth;
  });

  renderBills(filtered);
}

// Render bills
function renderBills(bills) {
  const tbody = document.getElementById("billsTableBody");
  if (!tbody) return;

  if (bills.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" style="text-align: center;">Không tìm thấy hóa đơn nào</td></tr>';
    return;
  }

  tbody.innerHTML = bills
    .map((bill) => {
      const statusClass = bill.status === "paid" ? "status-paid" : "status-unpaid";
      const statusText = bill.status === "paid" ? "Đã thanh toán" : "Chưa thanh toán";
      const billId = bill._id || bill.id;
      
      // Get tenant name
      const tenant = allTenants.find(t => (t._id || t.id) === bill.tenant_id);
      const tenantName = tenant ? tenant.name : bill.tenant_id;
      
      // Get room name
      const room = allRooms.find(r => (r._id || r.id) === bill.room_id);
      const roomName = room ? room.name : bill.room_id;
      
      return `
        <tr>
            <td><strong>${billId}</strong></td>
            <td>${tenantName}</td>
            <td>${roomName}</td>
            <td>${bill.month || ""}</td>
            <td>${formatPrice(bill.total_amount || 0)}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                <button class="btn-small btn-primary" onclick="openEditBillModal('${billId}')">Sửa</button>
                ${bill.status !== "paid" ? `<button class="btn-small btn-danger" onclick="deleteBill('${billId}')">Xóa</button>` : ""}
            </td>
        </tr>
    `;
    })
    .join("");
}

// Open create bill modal
window.openCreateBillModal = function openCreateBillModal() {
  currentEditId = null;
  const modal = document.getElementById("billModal");
  const form = document.getElementById("billForm");
  const title = document.getElementById("billModalTitle");
  const alert = document.getElementById("billModalAlert");
  
  if (title) title.textContent = "Tạo hóa đơn mới";
  if (form) form.reset();
  if (alert) {
    alert.style.display = "none";
    alert.className = "alert";
  }
  
  // Set current month as default
  const monthInput = document.getElementById("billMonth");
  if (monthInput) {
    const now = new Date();
    monthInput.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  }
  
  if (modal) modal.style.display = "block";
  loadTenantsAndRooms();
};

// Open edit bill modal
window.openEditBillModal = async function openEditBillModal(billId) {
  try {
    const headers = getAuthHeader();
    const response = await fetch(buildApiUrl(`/api/bills/${billId}`), {
      headers,
    });
    
    if (!response.ok) throw new Error("Không thể tải thông tin hóa đơn");
    const data = await response.json();
    const bill = data.bill || data;
    
    currentEditId = billId;
    const modal = document.getElementById("billModal");
    const form = document.getElementById("billForm");
    const title = document.getElementById("billModalTitle");
    const alert = document.getElementById("billModalAlert");
    
    if (title) title.textContent = "Sửa hóa đơn";
    if (alert) {
      alert.style.display = "none";
      alert.className = "alert";
    }
    
    // Fill form
    document.getElementById("billId").value = billId;
    document.getElementById("billTenantId").value = bill.tenant_id || "";
    document.getElementById("billRoomId").value = bill.room_id || "";
    document.getElementById("billMonth").value = bill.month || "";
    document.getElementById("billRoomPrice").value = bill.room_price || 0;
    document.getElementById("billElectricStart").value = bill.electric_start || 0;
    document.getElementById("billElectricEnd").value = bill.electric_end || 0;
    document.getElementById("billWaterStart").value = bill.water_start || 0;
    document.getElementById("billWaterEnd").value = bill.water_end || 0;
    document.getElementById("billElectricPrice").value = bill.electric_price || 3500;
    document.getElementById("billWaterPrice").value = bill.water_price || 20000;
    
    if (modal) modal.style.display = "block";
    await loadTenantsAndRooms();
    
    // Set values again after dropdowns are populated
    setTimeout(() => {
      document.getElementById("billTenantId").value = bill.tenant_id || "";
      document.getElementById("billRoomId").value = bill.room_id || "";
    }, 100);
  } catch (error) {
    console.error("Error loading bill:", error);
    alert("Không thể tải thông tin hóa đơn");
  }
};

// Close bill modal
window.closeBillModal = function closeBillModal() {
  const modal = document.getElementById("billModal");
  if (modal) modal.style.display = "none";
  const form = document.getElementById("billForm");
  if (form) form.reset();
  currentEditId = null;
};

// Delete bill
window.deleteBill = async function deleteBill(billId) {
  if (!confirm("Bạn có chắc chắn muốn xóa hóa đơn này?")) return;
  
  try {
    const headers = getAuthHeader();
    const response = await fetch(buildApiUrl(`/api/bills/${billId}`), {
      method: "DELETE",
      headers,
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || "Không thể xóa hóa đơn");
    }
    
    alert("Xóa hóa đơn thành công!");
    loadBillsData();
  } catch (error) {
    console.error("Error deleting bill:", error);
    alert(error.message || "Không thể xóa hóa đơn");
  }
};

// Handle bill form submission
document.addEventListener("DOMContentLoaded", function () {
  const billForm = document.getElementById("billForm");
  if (billForm) {
    billForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      
      const alert = document.getElementById("billModalAlert");
      const headers = getAuthHeader();
      
      const formData = {
        tenant_id: document.getElementById("billTenantId").value,
        room_id: document.getElementById("billRoomId").value,
        month: document.getElementById("billMonth").value,
        room_price: parseFloat(document.getElementById("billRoomPrice").value),
        electric_start: parseInt(document.getElementById("billElectricStart").value),
        electric_end: parseInt(document.getElementById("billElectricEnd").value),
        water_start: parseInt(document.getElementById("billWaterStart").value),
        water_end: parseInt(document.getElementById("billWaterEnd").value),
        electric_price: parseFloat(document.getElementById("billElectricPrice").value),
        water_price: parseFloat(document.getElementById("billWaterPrice").value),
      };
      
      try {
        let response;
        if (currentEditId) {
          // Update
          response = await fetch(buildApiUrl(`/api/bills/${currentEditId}`), {
            method: "PUT",
            headers,
            body: JSON.stringify(formData),
          });
        } else {
          // Create
        response = await fetch(buildApiUrl("/api/bills"), {
            method: "POST",
            headers,
            body: JSON.stringify(formData),
          });
        }
        
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.message || "Có lỗi xảy ra");
        }
        
        if (alert) {
          alert.className = "alert alert-success";
          alert.textContent = currentEditId ? "Cập nhật hóa đơn thành công!" : "Tạo hóa đơn thành công!";
          alert.style.display = "block";
        }
        
        setTimeout(() => {
          closeBillModal();
          loadBillsData();
        }, 1500);
      } catch (error) {
        console.error("Error saving bill:", error);
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = error.message || "Có lỗi xảy ra khi lưu hóa đơn";
          alert.style.display = "block";
        }
      }
    });
  }
  
  // Filter event listeners
  const searchInput = document.getElementById("billSearchInput");
  const statusFilter = document.getElementById("billStatusFilter");
  const monthFilter = document.getElementById("billMonthFilter");
  
  if (searchInput) {
    searchInput.addEventListener("input", filterBills);
  }
  if (statusFilter) {
    statusFilter.addEventListener("change", filterBills);
  }
  if (monthFilter) {
    monthFilter.addEventListener("change", filterBills);
  }
});

// Mark script as loaded
window.scriptsLoaded = window.scriptsLoaded || {};
window.scriptsLoaded.bills = true;
})();

