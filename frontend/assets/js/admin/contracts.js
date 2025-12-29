/**
 * Admin Contracts Page JavaScript
 * Basic operations:
 * - List contracts
 * - Update contract fields
 * - Extend end date
 * - Terminate contract
 */

let contracts = [];
let activeContract = null;

document.addEventListener("DOMContentLoaded", () => {
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  const form = document.getElementById("contractForm");
  if (form) form.addEventListener("submit", submitUpdate);

  refreshContracts();
});

function showSuccess(msg) {
  const el = document.getElementById("contractsSuccess");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2500);
}

function showError(msg) {
  const el = document.getElementById("contractsError");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError() {
  document.getElementById("contractsError")?.classList.add("hidden");
}

function showFormError(msg) {
  const el = document.getElementById("contractFormError");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearFormError() {
  document.getElementById("contractFormError")?.classList.add("hidden");
}

function formatMoney(v) {
  return new Intl.NumberFormat("vi-VN").format(v || 0) + " VNĐ";
}

function dateOnly(iso) {
  if (!iso) return "--";
  return String(iso).split("T")[0];
}

function statusBadge(status) {
  const st = String(status || "");
  if (st === "active")
    return {
      label: "Đang hoạt động",
      cls: "bg-green-100 text-green-700",
    };
  if (st === "terminated")
    return { label: "Đã kết thúc", cls: "bg-amber-100 text-amber-700" };
  if (st === "expired")
    return { label: "Hết hạn", cls: "bg-gray-100 text-gray-700" };
  return { label: st || "--", cls: "bg-gray-100 text-gray-700" };
}

async function refreshContracts() {
  clearError();
  UI.show("contractsLoading");
  UI.hide("contractsEmpty");
  UI.hide("contractsTable");

  const res = await API.get("/contracts");
  UI.hide("contractsLoading");

  if (!res.ok) {
    showError(res.data?.message || "Không thể tải danh sách hợp đồng");
    return;
  }

  contracts = res.data?.contracts || [];
  
  // Fetch user and room details for each contract
  for (const contract of contracts) {
    // Fetch user name
    if (contract.user_id) {
      try {
        const userRes = await API.get(`/users/${contract.user_id}`);
        if (userRes.ok && userRes.data) {
          contract.user_name = userRes.data.fullname || userRes.data.username || contract.user_id;
        }
      } catch (e) {
        contract.user_name = contract.user_id;
      }
    }
    
    // Fetch room code/name
    if (contract.room_id) {
      try {
        const roomRes = await API.get(`/rooms/${contract.room_id}`);
        if (roomRes.ok && roomRes.data) {
          contract.room_code = roomRes.data.code || roomRes.data.name || contract.room_id;
        }
      } catch (e) {
        contract.room_code = contract.room_id;
      }
    }
  }
  
  updateStats();

  if (!contracts.length) {
    UI.show("contractsEmpty");
    return;
  }

  renderTable();
  UI.show("contractsTable");
}

function updateStats() {
  const total = contracts.length;
  const active = contracts.filter((c) => c.status === "active").length;
  const terminated = contracts.filter((c) => c.status === "terminated").length;

  UI.setText("contractsTotal", total);
  UI.setText("contractsActive", active);
  UI.setText("contractsTerminated", terminated);
}

function renderTable() {
  const tbody = document.getElementById("contractsTbody");
  if (!tbody) return;

  tbody.innerHTML = contracts
    .map((c) => {
      const st = statusBadge(c.status);
      const range = `${dateOnly(c.start_date)} → ${dateOnly(c.end_date)}`;

      const canTerminate = c.status === "active";

      return `
        <tr class="hover:bg-gray-50 transition-colors">
          <td class="px-6 py-4 text-sm font-semibold text-gray-800">${escapeHtml(
            c._id || ""
          )}</td>
          <td class="px-6 py-4 text-sm text-gray-700">${escapeHtml(
            c.room_code || c.room_id || "--"
          )}</td>
          <td class="px-6 py-4 text-sm text-gray-700">${escapeHtml(
            c.user_name || c.user_id || "--"
          )}</td>
          <td class="px-6 py-4 text-sm text-gray-700">${escapeHtml(range)}</td>
          <td class="px-6 py-4 text-sm font-semibold text-indigo-600">${formatMoney(
            c.monthly_rent
          )}</td>
          <td class="px-6 py-4 text-sm">
            <span class="px-3 py-1 rounded-full text-xs font-semibold ${
              st.cls
            }">${st.label}</span>
          </td>
          <td class="px-6 py-4">
            <div class="flex items-center justify-center gap-2">
              <button
                onclick="openEditModal('${escapeAttr(c._id)}')"
                class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
                title="Cập nhật / Gia hạn"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                </svg>
              </button>
              <button
                onclick="terminateContract('${escapeAttr(c._id)}')"
                class="p-2 ${
                  canTerminate
                    ? "text-red-600 hover:bg-red-50"
                    : "text-gray-300"
                } rounded-lg"
                title="Kết thúc hợp đồng"
                ${canTerminate ? "" : "disabled"}
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function openEditModal(contractId) {
  activeContract = contracts.find((c) => c._id === contractId) || null;
  if (!activeContract) return;

  clearFormError();

  document.getElementById("editContractId").value = activeContract._id;
  UI.setText("editRoomId", activeContract.room_code || activeContract.room_id || "--");
  UI.setText("editUserId", activeContract.user_name || activeContract.user_id || "--");

  document.getElementById("editMonthlyRent").value =
    activeContract.monthly_rent || 0;
  document.getElementById("editDepositAmount").value =
    activeContract.deposit_amount || 0;
  document.getElementById("editDepositStatus").value =
    activeContract.deposit_status || "paid";
  document.getElementById("editPaymentDay").value =
    activeContract.payment_day || 5;
  document.getElementById("editNotes").value = activeContract.notes || "";

  document.getElementById("extendEndDate").value = "";

  const modal = document.getElementById("contractModal");
  if (modal) {
    modal.classList.add("active");
    modal.style.display = "flex";
  }
}

function closeContractModal() {
  const modal = document.getElementById("contractModal");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
  activeContract = null;
}

async function submitUpdate(e) {
  e.preventDefault();
  clearFormError();

  const contractId = document.getElementById("editContractId")?.value || "";
  if (!contractId) return;

  const payload = {
    monthly_rent:
      parseFloat(document.getElementById("editMonthlyRent")?.value) || 0,
    deposit_amount:
      parseFloat(document.getElementById("editDepositAmount")?.value) || 0,
    deposit_status:
      document.getElementById("editDepositStatus")?.value || "paid",
    payment_day:
      parseInt(document.getElementById("editPaymentDay")?.value, 10) || 5,
    notes: document.getElementById("editNotes")?.value?.trim() || "",
  };

  const btn = document.getElementById("contractSubmitBtn");
  const txt = document.getElementById("contractSubmitText");

  try {
    if (btn) btn.disabled = true;
    if (txt) txt.textContent = "Đang cập nhật...";

    const res = await API.put(
      `/contracts/${encodeURIComponent(contractId)}`,
      payload
    );
    if (!res.ok) {
      showFormError(res.data?.message || "Không thể cập nhật hợp đồng");
      return;
    }

    showSuccess("Cập nhật hợp đồng thành công!");
    closeContractModal();
    await refreshContracts();
  } catch (err) {
    console.error(err);
    showFormError("Lỗi kết nối server!");
  } finally {
    if (btn) btn.disabled = false;
    if (txt) txt.textContent = "Cập nhật";
  }
}

async function submitExtend() {
  clearFormError();

  const contractId = document.getElementById("editContractId")?.value || "";
  const newEndDate = document.getElementById("extendEndDate")?.value || "";

  if (!contractId || !newEndDate) {
    showFormError("Vui lòng chọn ngày kết thúc mới để gia hạn.");
    return;
  }

  try {
    const res = await API.put(
      `/contracts/${encodeURIComponent(contractId)}/extend`,
      {
        new_end_date: newEndDate,
      }
    );

    if (!res.ok) {
      showFormError(res.data?.message || "Không thể gia hạn hợp đồng");
      return;
    }

    showSuccess("Gia hạn hợp đồng thành công!");
    closeContractModal();
    await refreshContracts();
  } catch (err) {
    console.error(err);
    showFormError("Lỗi kết nối server!");
  }
}

async function terminateContract(contractId) {
  if (!contractId) return;
  if (!confirm(`Kết thúc hợp đồng ${contractId}?`)) return;

  try {
    const res = await API.put(
      `/contracts/${encodeURIComponent(contractId)}/terminate`,
      {}
    );
    if (!res.ok) {
      showError(res.data?.message || "Không thể kết thúc hợp đồng");
      return;
    }
    showSuccess("Kết thúc hợp đồng thành công!");
    await refreshContracts();
  } catch (err) {
    console.error(err);
    showError("Lỗi kết nối server!");
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(str) {
  return escapeHtml(str).replaceAll("`", "&#096;");
}
