let allTenants = [];
let allContracts = [];
let allRooms = [];
let currentEditTenantId = null;
let currentEditContractId = null;

// Helper functions - use window versions if available
function formatPrice(price) {
  if (typeof window.formatPrice === 'function') {
    return window.formatPrice(price);
  }
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(price);
}

function formatDate(dateString) {
  if (typeof window.formatDate === 'function') {
    return window.formatDate(dateString);
  }
  if (!dateString) return "-";
  const date = new Date(dateString);
  return date.toLocaleDateString("vi-VN");
}

// Switch tenant tab - expose immediately to window
function switchTenantTab(tab) {
  document
    .querySelectorAll("#tenantsPanel .tab")
    .forEach((t) => t.classList.remove("active"));
  const tenantsTabContent = document.getElementById("tenantsTabContent");
  const contractsTabContent = document.getElementById("contractsTabContent");

  if (tab === "tenants") {
    document.querySelectorAll("#tenantsPanel .tab")[0].classList.add("active");
    if (tenantsTabContent) tenantsTabContent.style.display = "block";
    if (contractsTabContent) contractsTabContent.style.display = "none";
    if (typeof loadTenantsData === 'function') {
      loadTenantsData();
    }
  } else {
    document.querySelectorAll("#tenantsPanel .tab")[1].classList.add("active");
    if (tenantsTabContent) tenantsTabContent.style.display = "none";
    if (contractsTabContent) contractsTabContent.style.display = "block";
    if (typeof loadContractsData === 'function') {
      loadContractsData();
    }
  }
}
window.switchTenantTab = switchTenantTab;

// Load tenants data
async function loadTenantsData() {
  console.log("loadTenantsData called from tenants.js");
  try {
    const headers = getAuthHeader();
    console.log("Fetching /api/tenants with headers:", headers);
    const response = await fetch("/api/tenants", {
      headers,
    });
    console.log("Tenants API response status:", response.status);
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách người thuê");
    const data = await response.json();
    console.log("Tenants data received:", data);
    allTenants = data.tenants || [];
    console.log("Total tenants loaded:", allTenants.length);
    filterTenants();
  } catch (error) {
    console.error("Error loading tenants:", error);
  }
}
window.loadTenantsData = loadTenantsData;

// Load contracts data
async function loadContractsData() {
  console.log("loadContractsData called from tenants.js");
  try {
    const headers = getAuthHeader();
    console.log("Fetching /api/contracts with headers:", headers);
    const response = await fetch("/api/contracts", {
      headers,
    });
    console.log("Contracts API response status:", response.status);
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách hợp đồng");
    const data = await response.json();
    console.log("Contracts data received:", data);
    allContracts = data.contracts || [];
    console.log("Total contracts loaded:", allContracts.length);
    filterContracts();
  } catch (error) {
    console.error("Error loading contracts:", error);
  }
}
window.loadContractsData = loadContractsData;

// Load rooms for contract form
async function loadRoomsForContract() {
  try {
    const response = await fetch("/api/rooms", {
      headers: getAuthHeader(),
    });
    if (!response.ok) throw new Error("Không thể tải danh sách phòng");
    const data = await response.json();
    allRooms = data.rooms.filter((r) => r.status === "available");
    const select = document.getElementById("contractRoomId");
    if (select) {
      select.innerHTML =
        '<option value="">Chọn phòng</option>' +
        allRooms
          .map(
            (r) =>
              `<option value="${r._id}">${r.name} - ${formatPrice(
                r.price
              )}/tháng</option>`
          )
          .join("");
    }
  } catch (error) {
    console.error("Error loading rooms:", error);
  }
}

// Filter tenants
function filterTenants() {
  const searchInput = document.getElementById("tenantSearchInput");
  const statusFilter = document.getElementById("tenantStatusFilter");

  if (!searchInput || !statusFilter) return;

  const searchText = searchInput.value.toLowerCase();
  const statusFilterValue = statusFilter.value;

  let filtered = allTenants.filter((tenant) => {
    const matchSearch =
      tenant.name.toLowerCase().includes(searchText) ||
      tenant.phone.includes(searchText) ||
      tenant.id_card.includes(searchText);
    const matchStatus =
      !statusFilterValue || tenant.status === statusFilterValue;
    return matchSearch && matchStatus;
  });

  renderTenants(filtered);
}

// Render tenants
function renderTenants(tenants) {
  const tbody = document.getElementById("tenantsTableBody");
  if (!tbody) return;

  if (tenants.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="6" style="text-align: center;">Không tìm thấy người thuê nào</td></tr>';
    return;
  }

  tbody.innerHTML = tenants
    .map((tenant) => {
      const statusClass = `status-${tenant.status}`;
      const statusText =
        tenant.status === "active" ? "Đang hoạt động" : "Ngừng hoạt động";
      return `
        <tr>
            <td>${tenant._id}</td>
            <td><strong>${tenant.name}</strong></td>
            <td>${tenant.phone}</td>
            <td>${tenant.id_card}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                <button class="btn-action btn-view" onclick="viewTenant('${tenant._id}')">Xem</button>
                <button class="btn-action btn-edit" onclick="openEditTenantModal('${tenant._id}')">Sửa</button>
                <button class="btn-action btn-delete" onclick="deleteTenant('${tenant._id}')">Xóa</button>
            </td>
        </tr>
    `;
    })
    .join("");
}

// Filter contracts
function filterContracts() {
  const searchInput = document.getElementById("contractSearchInput");
  const statusFilter = document.getElementById("contractStatusFilter");

  if (!searchInput || !statusFilter) return;

  const searchText = searchInput.value.toLowerCase();
  const statusFilterValue = statusFilter.value;

  let filtered = allContracts.filter((contract) => {
    const matchSearch =
      contract.tenant_name?.toLowerCase().includes(searchText) ||
      contract.room_id.toLowerCase().includes(searchText);
    const matchStatus =
      !statusFilterValue || contract.status === statusFilterValue;
    return matchSearch && matchStatus;
  });

  renderContracts(filtered);
}

// Render contracts
function renderContracts(contracts) {
  const tbody = document.getElementById("contractsTableBody");
  if (!tbody) return;

  if (contracts.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" style="text-align: center;">Không tìm thấy hợp đồng nào</td></tr>';
    return;
  }

  tbody.innerHTML = contracts
    .map((contract) => {
      const statusClass = `status-${contract.status}`;
      const statusText =
        {
          active: "Đang hoạt động",
          expired: "Hết hạn",
          terminated: "Đã chấm dứt",
        }[contract.status] || contract.status;
      return `
        <tr>
            <td>${contract._id}</td>
            <td>${contract.tenant_name || "-"}</td>
            <td>${contract.room_id}</td>
            <td>${formatDate(contract.start_date)}</td>
            <td>${formatDate(contract.end_date)}</td>
            <td>${formatPrice(contract.monthly_rent)}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                <button class="btn-action btn-view" onclick="viewContract('${
                  contract._id
                }')">Xem</button>
                ${
                  contract.status === "active"
                    ? `<button class="btn-action btn-edit" onclick="terminateContract('${contract._id}')">Chấm dứt</button>`
                    : ""
                }
            </td>
        </tr>
    `;
    })
    .join("");
}

// Open create tenant modal
function openCreateTenantModal() {
  currentEditTenantId = null;
  const modalTitle = document.getElementById("tenantModalTitle");
  const tenantForm = document.getElementById("tenantForm");
  const tenantId = document.getElementById("tenantId");
  const modalAlert = document.getElementById("tenantModalAlert");

  if (modalTitle) modalTitle.textContent = "Thêm người thuê mới";
  if (tenantForm) tenantForm.reset();
  if (tenantId) tenantId.value = "";
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("tenantModal");
  if (modal) modal.style.display = "block";
}
window.openCreateTenantModal = openCreateTenantModal;

// Open edit tenant modal
function openEditTenantModal(tenantId) {
  const tenant = allTenants.find((t) => t._id === tenantId);
  if (!tenant) return;

  currentEditTenantId = tenantId;
  const modalTitle = document.getElementById("tenantModalTitle");
  const tenantIdInput = document.getElementById("tenantId");
  const tenantName = document.getElementById("tenantName");
  const tenantPhone = document.getElementById("tenantPhone");
  const tenantIdCard = document.getElementById("tenantIdCard");
  const tenantAddress = document.getElementById("tenantAddress");
  const tenantEmail = document.getElementById("tenantEmail");
  const tenantDob = document.getElementById("tenantDob");
  const tenantStatus = document.getElementById("tenantStatus");
  const modalAlert = document.getElementById("tenantModalAlert");

  if (modalTitle) modalTitle.textContent = "Chỉnh sửa người thuê";
  if (tenantIdInput) tenantIdInput.value = tenantId;
  if (tenantName) tenantName.value = tenant.name;
  if (tenantPhone) tenantPhone.value = tenant.phone;
  if (tenantIdCard) tenantIdCard.value = tenant.id_card;
  if (tenantAddress) tenantAddress.value = tenant.address;
  if (tenantEmail) tenantEmail.value = tenant.email || "";
  if (tenantDob) tenantDob.value = tenant.date_of_birth || "";
  if (tenantStatus) tenantStatus.value = tenant.status;
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("tenantModal");
  if (modal) modal.style.display = "block";
}
window.openEditTenantModal = openEditTenantModal;

// Close tenant modal
function closeTenantModal() {
  const modal = document.getElementById("tenantModal");
  if (modal) modal.style.display = "none";
}
window.closeTenantModal = closeTenantModal;

// Delete tenant
async function deleteTenant(tenantId) {
  if (!confirm("Bạn có chắc muốn xóa người thuê này?")) return;
  try {
    const response = await fetch(`/api/tenants/${tenantId}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    alert(data.message);
    loadTenantsData();
  } catch (error) {
    alert(error.message);
  }
}
window.deleteTenant = deleteTenant;

// View tenant
async function viewTenant(tenantId) {
  try {
    const response = await fetch(`/api/tenants/${tenantId}`, {
      headers: getAuthHeader(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    alert(
      `Thông tin người thuê:\n\nTên: ${data.name}\nSĐT: ${data.phone}\nCMND: ${
        data.id_card
      }\nĐịa chỉ: ${data.address}\n\nHợp đồng: ${
        data.contracts?.length || 0
      } hợp đồng`
    );
  } catch (error) {
    alert(error.message);
  }
}
window.viewTenant = viewTenant;

// Open create contract modal
async function openCreateContractModal() {
  await loadRoomsForContract();
  await loadTenantsData();

  currentEditContractId = null;
  const modalTitle = document.getElementById("contractModalTitle");
  const contractForm = document.getElementById("contractForm");
  const contractId = document.getElementById("contractId");
  const tenantSelect = document.getElementById("contractTenantId");
  const modalAlert = document.getElementById("contractModalAlert");

  if (modalTitle) modalTitle.textContent = "Tạo hợp đồng mới";
  if (contractForm) contractForm.reset();
  if (contractId) contractId.value = "";
  if (tenantSelect) {
    tenantSelect.innerHTML =
      '<option value="">Chọn người thuê</option>' +
      allTenants
        .filter((t) => t.status === "active")
        .map((t) => `<option value="${t._id}">${t.name} - ${t.phone}</option>`)
        .join("");
  }
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("contractModal");
  if (modal) modal.style.display = "block";
}
window.openCreateContractModal = openCreateContractModal;

// Close contract modal
function closeContractModal() {
  const modal = document.getElementById("contractModal");
  if (modal) modal.style.display = "none";
}
window.closeContractModal = closeContractModal;

// View contract
async function viewContract(contractId) {
  try {
    const response = await fetch(`/api/contracts/${contractId}`, {
      headers: getAuthHeader(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    alert(
      `Thông tin hợp đồng:\n\nMã: ${data._id}\nNgười thuê: ${
        data.tenant_info?.name
      }\nPhòng: ${data.room_id}\nTừ: ${formatDate(
        data.start_date
      )} đến ${formatDate(data.end_date)}\nGiá thuê: ${formatPrice(
        data.monthly_rent
      )}/tháng`
    );
  } catch (error) {
    alert(error.message);
  }
}
window.viewContract = viewContract;

// Terminate contract
async function terminateContract(contractId) {
  if (!confirm("Bạn có chắc muốn chấm dứt hợp đồng này?")) return;
  try {
    const response = await fetch(`/api/contracts/${contractId}/terminate`, {
      method: "PUT",
      headers: getAuthHeader(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    alert(data.message);
    loadContractsData();
    // Reload rooms to update status
    if (typeof loadRoomsData === "function") {
      loadRoomsData();
    }
  } catch (error) {
    alert(error.message);
  }
}
window.terminateContract = terminateContract;

// Initialize tenant form handlers
function initializeTenantsHandlers() {
  console.log("initializeTenantsHandlers called from tenants.js");
  const tenantForm = document.getElementById("tenantForm");
  if (tenantForm && !tenantForm.dataset.initialized) {
    console.log("Initializing tenant form handler");
    tenantForm.dataset.initialized = "true";
    tenantForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const tenantName = document.getElementById("tenantName");
      const tenantPhone = document.getElementById("tenantPhone");
      const tenantIdCard = document.getElementById("tenantIdCard");
      const tenantAddress = document.getElementById("tenantAddress");
      const tenantEmail = document.getElementById("tenantEmail");
      const tenantDob = document.getElementById("tenantDob");
      const tenantStatus = document.getElementById("tenantStatus");

      if (!tenantName || !tenantPhone || !tenantIdCard || !tenantAddress)
        return;

      const formData = {
        name: tenantName.value,
        phone: tenantPhone.value,
        id_card: tenantIdCard.value,
        address: tenantAddress.value,
        email: tenantEmail ? tenantEmail.value : "",
        date_of_birth: tenantDob ? tenantDob.value : "",
        status: tenantStatus ? tenantStatus.value : "active",
      };

      const modalAlert = document.getElementById("tenantModalAlert");
      try {
        const url = currentEditTenantId
          ? `/api/tenants/${currentEditTenantId}`
          : "/api/tenants";
        const method = currentEditTenantId ? "PUT" : "POST";
        const response = await fetch(url, {
          method: method,
          headers: {
            ...getAuthHeader(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify(formData),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);

        if (modalAlert) {
          modalAlert.className = "alert alert-success";
          modalAlert.textContent = data.message;
          modalAlert.style.display = "block";
        }

        setTimeout(() => {
          closeTenantModal();
          loadTenantsData();
        }, 1500);
      } catch (error) {
        if (modalAlert) {
          modalAlert.className = "alert alert-error";
          modalAlert.textContent = error.message;
          modalAlert.style.display = "block";
        }
      }
    });
  }

  // Contract form
  const contractForm = document.getElementById("contractForm");
  if (contractForm && !contractForm.dataset.initialized) {
    console.log("Initializing contract form handler");
    contractForm.dataset.initialized = "true";
    contractForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const contractTenantId = document.getElementById("contractTenantId");
      const contractRoomId = document.getElementById("contractRoomId");
      const contractStartDate = document.getElementById("contractStartDate");
      const contractEndDate = document.getElementById("contractEndDate");
      const contractMonthlyRent = document.getElementById(
        "contractMonthlyRent"
      );
      const contractDeposit = document.getElementById("contractDeposit");
      const contractElectricPrice = document.getElementById(
        "contractElectricPrice"
      );
      const contractWaterPrice = document.getElementById("contractWaterPrice");
      const contractPaymentDay = document.getElementById("contractPaymentDay");
      const contractNotes = document.getElementById("contractNotes");

      if (
        !contractTenantId ||
        !contractRoomId ||
        !contractStartDate ||
        !contractEndDate ||
        !contractMonthlyRent ||
        !contractDeposit
      )
        return;

      const formData = {
        tenant_id: contractTenantId.value,
        room_id: contractRoomId.value,
        start_date: contractStartDate.value,
        end_date: contractEndDate.value,
        monthly_rent: parseFloat(contractMonthlyRent.value),
        deposit: parseFloat(contractDeposit.value),
        electric_price: contractElectricPrice
          ? parseFloat(contractElectricPrice.value)
          : 3500,
        water_price: contractWaterPrice
          ? parseFloat(contractWaterPrice.value)
          : 20000,
        payment_day: contractPaymentDay
          ? parseInt(contractPaymentDay.value)
          : 5,
        notes: contractNotes ? contractNotes.value : "",
      };

      const modalAlert = document.getElementById("contractModalAlert");
      try {
        const response = await fetch("/api/contracts", {
          method: "POST",
          headers: {
            ...getAuthHeader(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify(formData),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message);

        if (modalAlert) {
          modalAlert.className = "alert alert-success";
          modalAlert.textContent = data.message;
          modalAlert.style.display = "block";
        }

        setTimeout(() => {
          closeContractModal();
          loadContractsData();
          if (typeof loadRoomsData === "function") {
            loadRoomsData();
          }
        }, 1500);
      } catch (error) {
        if (modalAlert) {
          modalAlert.className = "alert alert-error";
          modalAlert.textContent = error.message;
          modalAlert.style.display = "block";
        }
      }
    });
  }

  // Search and filter handlers
  const tenantSearchInput = document.getElementById("tenantSearchInput");
  const tenantStatusFilter = document.getElementById("tenantStatusFilter");
  const contractSearchInput = document.getElementById("contractSearchInput");
  const contractStatusFilter = document.getElementById("contractStatusFilter");

  if (tenantSearchInput && !tenantSearchInput.dataset.initialized) {
    tenantSearchInput.dataset.initialized = "true";
    tenantSearchInput.addEventListener("input", filterTenants);
  }
  if (tenantStatusFilter && !tenantStatusFilter.dataset.initialized) {
    tenantStatusFilter.dataset.initialized = "true";
    tenantStatusFilter.addEventListener("change", filterTenants);
  }
  if (contractSearchInput && !contractSearchInput.dataset.initialized) {
    contractSearchInput.dataset.initialized = "true";
    contractSearchInput.addEventListener("input", filterContracts);
  }
  if (contractStatusFilter && !contractStatusFilter.dataset.initialized) {
    contractStatusFilter.dataset.initialized = "true";
    contractStatusFilter.addEventListener("change", filterContracts);
  }

  // Close modals on outside click - only set once
  if (!window.tenantsModalClickHandler) {
    window.tenantsModalClickHandler = function (event) {
      const tenantModal = document.getElementById("tenantModal");
      const contractModal = document.getElementById("contractModal");
      if (event.target === tenantModal && tenantModal) {
        closeTenantModal();
      }
      if (event.target === contractModal && contractModal) {
        closeContractModal();
      }
    };
    window.addEventListener("click", window.tenantsModalClickHandler);
  }
}
window.initializeTenantsHandlers = initializeTenantsHandlers;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", function () {
  // Initialize immediately if panel is already visible
  if (document.getElementById("tenantsPanel")) {
    initializeTenantsHandlers();
  }
});
