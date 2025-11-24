let allTenants = [];
let currentEditTenantId = null;

// Expose functions to window
window.openCreateTenantModal = function openCreateTenantModal() {
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
};

window.switchTenantTab = function switchTenantTab(tab) {
  // This function is kept for backward compatibility if needed, 
  // but with the new separate panels, it might not be used anymore 
  // for switching between tenants/contracts/bookings within the tenant panel.
  // However, the admin.js might still call it if we didn't update all references.
  // Since we split the panels, we don't need tab switching logic for tenants panel anymore.
  // I will leave an empty or deprecated function just in case.
  console.warn("switchTenantTab is deprecated. Use navigateToSection instead.");
};

window.loadTenantsData = async function loadTenantsData() {
  console.log("loadTenantsData called from tenants.js");
  try {
    const headers = getAuthHeader();
    const response = await fetch("/api/tenants", { headers });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách người thuê");
    const data = await response.json();
    allTenants = data.tenants || [];
    filterTenants();
  } catch (error) {
    console.error("Error loading tenants:", error);
  }
};

window.openEditTenantModal = function openEditTenantModal(tenantId) {
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
  const tenantUsername = document.getElementById("tenantUsername");
  const tenantPassword = document.getElementById("tenantPassword");
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
  if (tenantUsername) tenantUsername.value = tenant.username || "";
  if (tenantPassword) tenantPassword.value = ""; 
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("tenantModal");
  if (modal) modal.style.display = "block";
};

window.closeTenantModal = function closeTenantModal() {
  const modal = document.getElementById("tenantModal");
  if (modal) modal.style.display = "none";
};

window.deleteTenant = async function deleteTenant(tenantId) {
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
};

window.viewTenant = async function viewTenant(tenantId) {
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
};

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

function initializeTenantsHandlers() {
  console.log("initializeTenantsHandlers called from tenants.js");
  const tenantForm = document.getElementById("tenantForm");
  if (tenantForm && !tenantForm.dataset.initialized) {
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
      const tenantUsername = document.getElementById("tenantUsername");
      const tenantPassword = document.getElementById("tenantPassword");

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
        create_account: true, 
      };

      if (tenantUsername && tenantUsername.value.trim()) {
        formData.username = tenantUsername.value.trim();
      }
      if (tenantPassword && tenantPassword.value.trim()) {
        formData.password = tenantPassword.value.trim();
      }

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
          let successMsg = data.message;
          if (data.tenant && data.tenant.username) {
            successMsg += `\nTên đăng nhập: ${data.tenant.username}`;
            if (!tenantPassword || !tenantPassword.value.trim()) {
              successMsg += `\nMật khẩu mặc định: 123456`;
            }
          } else if (data.username) {
            successMsg += `\nTên đăng nhập: ${data.username}`;
            if (!tenantPassword || !tenantPassword.value.trim()) {
              successMsg += `\nMật khẩu mặc định: 123456`;
            }
          }
          modalAlert.textContent = successMsg;
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

  const tenantSearchInput = document.getElementById("tenantSearchInput");
  const tenantStatusFilter = document.getElementById("tenantStatusFilter");

  if (tenantSearchInput && !tenantSearchInput.dataset.initialized) {
    tenantSearchInput.dataset.initialized = "true";
    tenantSearchInput.addEventListener("input", filterTenants);
  }
  if (tenantStatusFilter && !tenantStatusFilter.dataset.initialized) {
    tenantStatusFilter.dataset.initialized = "true";
    tenantStatusFilter.addEventListener("change", filterTenants);
  }

  // Close modals on outside click
  if (!window.tenantsModalClickHandler) {
    window.tenantsModalClickHandler = function (event) {
      const tenantModal = document.getElementById("tenantModal");
      if (event.target === tenantModal && tenantModal) {
        closeTenantModal();
      }
    };
    window.addEventListener("click", window.tenantsModalClickHandler);
  }
}

window.initializeTenantsHandlers = initializeTenantsHandlers;

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("tenantsPanel")) {
    initializeTenantsHandlers();
  }
});

// Notify that tenants.js is ready
if (typeof window.scriptsLoaded === "undefined") {
  window.scriptsLoaded = {};
}
window.scriptsLoaded.tenants = true;
console.log("tenants.js loaded");
