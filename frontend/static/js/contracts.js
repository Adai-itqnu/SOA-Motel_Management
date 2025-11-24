let allContracts = [];
let currentEditContractId = null;

// Expose functions to window
window.openCreateContractModal = async function openCreateContractModal() {
  // Load rooms and tenants data first
  if (typeof loadRoomsForContract === "function") {
    try {
      await loadRoomsForContract();
    } catch (e) {
      console.error("Error loading rooms:", e);
    }
  }
  if (typeof loadTenantsData === "function") {
    try {
      await loadTenantsData();
    } catch (e) {
      console.error("Error loading tenants:", e);
    }
  }

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
    // We need allTenants from tenants.js. 
    // Since tenants.js runs first or we wait for it, we can access window.allTenants if we expose it, 
    // or we just rely on the select being populated if loadTenantsData populated a global list.
    // Actually, loadTenantsData in tenants.js populates 'allTenants' local variable there. 
    // We should probably expose allTenants in tenants.js or just fetch it here.
    // For now, let's assume loadTenantsData populates the select if we call it? 
    // No, loadTenantsData populates the table. 
    // We need to populate the select box here.
    // Let's rely on a helper or just fetch tenants again if needed, but better to share data.
    // For this refactor, I will assume we can fetch or use a global. 
    // Let's look at how it was done: it used 'allTenants' which was local to tenants.js.
    // I will need to update tenants.js to expose allTenants or fetch it here.
    // I will fetch it here to be safe and independent.
    
    try {
        const response = await fetch("/api/tenants", { headers: getAuthHeader() });
        if (response.ok) {
            const data = await response.json();
            const tenants = data.tenants || [];
            tenantSelect.innerHTML =
              '<option value="">Chọn người thuê</option>' +
              tenants
                .filter((t) => t.status === "active")
                .map((t) => `<option value="${t._id}">${t.name} - ${t.phone}</option>`)
                .join("");
        }
    } catch (e) {
        console.error("Error fetching tenants for dropdown:", e);
    }
  }
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("contractModal");
  if (modal) modal.style.display = "block";
};

window.closeContractModal = function closeContractModal() {
  const modal = document.getElementById("contractModal");
  if (modal) modal.style.display = "none";
};

window.loadContractsData = async function loadContractsData() {
  console.log("loadContractsData called");
  try {
    const headers = getAuthHeader();
    const response = await fetch("/api/contracts", { headers });
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách hợp đồng");
    const data = await response.json();
    allContracts = data.contracts || [];
    filterContracts();
  } catch (error) {
    console.error("Error loading contracts:", error);
  }
};

window.viewContract = async function viewContract(contractId) {
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
};

window.terminateContract = async function terminateContract(contractId) {
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
    // Reload rooms to update status if rooms.js is loaded
    if (typeof loadRoomsData === "function") {
      loadRoomsData();
    }
  } catch (error) {
    alert(error.message);
  }
};

// Helper to load rooms for the dropdown
async function loadRoomsForContract() {
  try {
    const response = await fetch("/api/rooms", {
      headers: getAuthHeader(),
    });
    if (!response.ok) throw new Error("Không thể tải danh sách phòng");
    const data = await response.json();
    const availableRooms = data.rooms.filter((r) => r.status === "available");
    const select = document.getElementById("contractRoomId");
    if (select) {
      select.innerHTML =
        '<option value="">Chọn phòng</option>' +
        availableRooms
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

function initializeContractsHandlers() {
  console.log("initializeContractsHandlers called");
  const contractForm = document.getElementById("contractForm");
  if (contractForm && !contractForm.dataset.initialized) {
    contractForm.dataset.initialized = "true";
    contractForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const contractTenantId = document.getElementById("contractTenantId");
      const contractRoomId = document.getElementById("contractRoomId");
      const contractStartDate = document.getElementById("contractStartDate");
      const contractEndDate = document.getElementById("contractEndDate");
      const contractMonthlyRent = document.getElementById("contractMonthlyRent");
      const contractDeposit = document.getElementById("contractDeposit");
      const contractElectricPrice = document.getElementById("contractElectricPrice");
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
  const contractSearchInput = document.getElementById("contractSearchInput");
  const contractStatusFilter = document.getElementById("contractStatusFilter");

  if (contractSearchInput && !contractSearchInput.dataset.initialized) {
    contractSearchInput.dataset.initialized = "true";
    contractSearchInput.addEventListener("input", filterContracts);
  }
  if (contractStatusFilter && !contractStatusFilter.dataset.initialized) {
    contractStatusFilter.dataset.initialized = "true";
    contractStatusFilter.addEventListener("change", filterContracts);
  }
  
  // Close modal on outside click
  if (!window.contractsModalClickHandler) {
      window.contractsModalClickHandler = function (event) {
        const contractModal = document.getElementById("contractModal");
        if (event.target === contractModal && contractModal) {
          closeContractModal();
        }
      };
      window.addEventListener("click", window.contractsModalClickHandler);
  }
}

// Initialize on DOM ready or when script loaded
document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("contractsPanel")) {
    initializeContractsHandlers();
  }
});

// Notify that contracts.js is ready
if (typeof window.scriptsLoaded === "undefined") {
  window.scriptsLoaded = {};
}
window.scriptsLoaded.contracts = true;
console.log("contracts.js loaded");
