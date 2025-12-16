/**
 * Admin Room Management JavaScript
 * Simplified to match backend API requirements
 */

let allRooms = [];
let filteredRooms = [];
let deleteRoomId = null;

// ============== INITIALIZATION ==============
document.addEventListener("DOMContentLoaded", () => {
  // Init layout (includes auth check)
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  loadRooms();

  // Form submit handler
  const form = document.getElementById("roomForm");
  if (form) {
    form.addEventListener("submit", handleSubmit);
  }

  // Contract form submit handler
  const contractForm = document.getElementById("contractForm");
  if (contractForm) {
    contractForm.addEventListener("submit", handleContractSubmit);
  }
});

// ============== LOAD ROOMS ==============
async function loadRooms() {
  try {
    const res = await API.get("/rooms");
    if (res.ok) {
      allRooms = res.data.rooms || res.data || [];
      filteredRooms = [...allRooms];
      renderRooms();
      updateStats();
    } else {
      showTableError(res.data.message || "Không thể tải danh sách phòng");
    }
  } catch (error) {
    console.error("Error loading rooms:", error);
    showTableError("Lỗi kết nối server");
  }
}

function updateStats() {
  UI.setText("totalRooms", allRooms.length);
  UI.setText(
    "availableRooms",
    allRooms.filter((r) => r.status === "available").length
  );
  UI.setText(
    "occupiedRooms",
    allRooms.filter((r) => r.status === "occupied").length
  );
  UI.setText(
    "maintenanceRooms",
    allRooms.filter((r) => r.status === "maintenance").length
  );
}

function renderRooms() {
  const tbody = document.getElementById("roomTableBody");
  if (!tbody) return;

  if (filteredRooms.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-6 py-8 text-center text-gray-400">
                    <svg class="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                    </svg>
                    <p>Chưa có phòng nào</p>
                    <button onclick="openAddModal()" class="mt-2 text-indigo-600 hover:underline">+ Thêm phòng mới</button>
                </td>
            </tr>
        `;
    return;
  }

  tbody.innerHTML = filteredRooms
    .map(
      (room) => `
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center">
                        <span class="text-indigo-600 font-bold text-sm">${(
                          room.name || "P"
                        ).charAt(0)}</span>
                    </div>
                    <div>
                        <p class="font-semibold text-gray-800">${
                          room.name || "N/A"
                        }</p>
                        <p class="text-sm text-gray-400">${
                          room.description || ""
                        }</p>
                    </div>
                </div>
            </td>
            <td class="px-6 py-4 text-gray-600">${getRoomTypeLabel(
              room.room_type
            )}</td>
            <td class="px-6 py-4 font-semibold text-indigo-600">${formatCurrency(
              room.price
            )}</td>
            <td class="px-6 py-4">${getStatusBadge(room.status)}</td>
            <td class="px-6 py-4">
                <div class="flex items-center justify-center gap-2">
                    ${
                      room.status === "reserved" &&
                      room.reserved_by_tenant_id &&
                      String(room.reservation_status || "") === "paid"
                        ? `<button onclick="openContractModal('${room._id}')" class="p-2 text-purple-700 hover:bg-purple-50 rounded-lg" title="Tạo hợp đồng">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                          </button>`
                        : ""
                    }
                    <button onclick="openEditModal('${
                      room._id
                    }')" class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg" title="Sửa">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                        </svg>
                    </button>
                    <button onclick="openDeleteModal('${room._id}', '${
        room.name
      }')" class="p-2 text-red-600 hover:bg-red-50 rounded-lg" title="Xóa">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    `
    )
    .join("");
}

function getRoomTypeLabel(type) {
  const types = {
    single: "Phòng đơn",
    double: "Phòng đôi",
    studio: "Studio",
    apartment: "Căn hộ",
  };
  return types[type] || type || "Khác";
}

function getStatusBadge(status) {
  const badges = {
    available:
      '<span class="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">Còn trống</span>',
    reserved:
      '<span class="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium">Đang giữ</span>',
    occupied:
      '<span class="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">Đang thuê</span>',
    maintenance:
      '<span class="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">Bảo trì</span>',
  };
  return (
    badges[status] ||
    '<span class="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">Khác</span>'
  );
}

function formatCurrency(amount) {
  if (!amount) return "0 VNĐ";
  return new Intl.NumberFormat("vi-VN").format(amount) + " VNĐ";
}

function showTableError(message) {
  const tbody = document.getElementById("roomTableBody");
  if (tbody) {
    tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-6 py-8 text-center text-red-500">
                    <p>⚠️ ${message}</p>
                    <button onclick="loadRooms()" class="mt-2 text-indigo-600 hover:underline">Thử lại</button>
                </td>
            </tr>
        `;
  }
}

// ============== SEARCH & FILTER ==============
function handleSearch() {
  applyFilters();
}

function handleFilter() {
  applyFilters();
}

function applyFilters() {
  const search =
    document.getElementById("searchInput")?.value?.toLowerCase() || "";
  const status = document.getElementById("statusFilter")?.value || "";
  const type = document.getElementById("typeFilter")?.value || "";
  const priceSort = document.getElementById("priceSort")?.value || "";

  filteredRooms = allRooms.filter((room) => {
    const matchSearch =
      !search || (room.name || "").toLowerCase().includes(search);
    const matchStatus = !status || room.status === status;
    const matchType = !type || room.room_type === type;
    return matchSearch && matchStatus && matchType;
  });

  if (priceSort === "asc") {
    filteredRooms.sort((a, b) => (a.price || 0) - (b.price || 0));
  } else if (priceSort === "desc") {
    filteredRooms.sort((a, b) => (b.price || 0) - (a.price || 0));
  }

  renderRooms();
}

// ============== ADD/EDIT MODAL ==============
function openAddModal() {
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
    else console.warn(`[rooms] Missing element #${id}`);
  };
  const setValue = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value;
    else console.warn(`[rooms] Missing element #${id}`);
  };

  setText("modalTitle", "Thêm phòng mới");
  setText("submitText", "Thêm phòng");
  setValue("roomId", "");

  const form = document.getElementById("roomForm");
  if (form) form.reset();
  else console.warn("[rooms] Missing element #roomForm");

  document.getElementById("formError")?.classList.add("hidden");

  // Set defaults
  setValue("electricPrice", 3500);
  setValue("waterPrice", 15000);
  setValue("roomDeposit", 0);
  setValue("roomArea", 0);
  setValue("roomFloor", 1);
  // Clear checkbox amenities
  document.querySelectorAll('input[name="amenities"]').forEach(cb => cb.checked = false);
  const imagesEl = document.getElementById("roomImages");
  if (imagesEl) imagesEl.value = "";

  const modal = document.getElementById("roomModal");
  if (modal) {
    modal.classList.add("active");
    // If modal CSS from layout isn't present, force visibility
    modal.style.display = "flex";
  }
}

function openEditModal(roomId) {
  const room = allRooms.find((r) => r._id === roomId);
  if (!room) return;

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
    else console.warn(`[rooms] Missing element #${id}`);
  };
  const setValue = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value;
    else console.warn(`[rooms] Missing element #${id}`);
  };

  setText("modalTitle", "Chỉnh sửa phòng");
  setText("submitText", "Cập nhật");
  setValue("roomId", roomId);
  document.getElementById("formError")?.classList.add("hidden");

  // Fill form with room data
  setValue("roomName", room.name || "");
  setValue("roomType", room.room_type || "single");
  setValue("roomPrice", room.price || "");
  setValue("electricPrice", room.electricity_price || room.electric_price || 3500);
  setValue("waterPrice", room.water_price || 15000);
  setValue("roomDeposit", room.deposit || 0);
  setValue("roomArea", room.area || room.area_m2 || 0);
  setValue("roomFloor", room.floor || 1);
  setValue("roomDescription", room.description || "");

  // Set checkbox amenities
  const roomAmenities = new Set((room.amenities || []).map(String));
  document.querySelectorAll('input[name="amenities"]').forEach(cb => {
    cb.checked = roomAmenities.has(cb.value);
  });

  const imagesEl = document.getElementById("roomImages");
  if (imagesEl) imagesEl.value = "";

  const modal = document.getElementById("roomModal");
  if (modal) {
    modal.classList.add("active");
    modal.style.display = "flex";
  }
}

function closeModal() {
  const modal = document.getElementById("roomModal");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

// ============== CONTRACT MODAL ==============
function openContractModal(roomId) {
  const room = allRooms.find((r) => r._id === roomId);
  if (!room) return;

  const tenantId = room.reserved_by_tenant_id;
  if (!tenantId) {
    alert("Phòng này chưa có người giữ phòng.");
    return;
  }

  // Default dates: today -> +1 year
  const today = new Date();
  const startDate = `${today.getFullYear()}-${String(
    today.getMonth() + 1
  ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const end = new Date(today);
  end.setFullYear(end.getFullYear() + 1);
  const endDate = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(
    2,
    "0"
  )}-${String(end.getDate()).padStart(2, "0")}`;

  document.getElementById("contractRoomId").value = roomId;
  UI.setText("contractRoomName", room.name || roomId);
  UI.setText("contractUserId", tenantId);

  document.getElementById("contractStartDate").value = startDate;
  document.getElementById("contractEndDate").value = endDate;
  document.getElementById("contractMonthlyRent").value = room.price || 0;
  document.getElementById("contractDepositAmount").value = room.deposit || 0;
  document.getElementById("contractPaymentDay").value = 5;
  document.getElementById("contractNotes").value = "";

  document.getElementById("contractFormError").classList.add("hidden");

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
}

function showContractFormError(message) {
  const el = document.getElementById("contractFormError");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
}

async function handleContractSubmit(e) {
  e.preventDefault();

  const roomId = document.getElementById("contractRoomId")?.value || "";
  const startDate = document.getElementById("contractStartDate")?.value || "";
  const endDate = document.getElementById("contractEndDate")?.value || "";
  const monthlyRent =
    parseFloat(document.getElementById("contractMonthlyRent")?.value) || 0;
  const depositAmount =
    parseFloat(document.getElementById("contractDepositAmount")?.value) || 0;
  const paymentDay =
    parseInt(document.getElementById("contractPaymentDay")?.value, 10) || 5;
  const notes = document.getElementById("contractNotes")?.value?.trim() || "";

  if (!roomId || !startDate || !endDate || !monthlyRent) {
    showContractFormError(
      "Vui lòng nhập đủ: Ngày bắt đầu, Ngày kết thúc, Giá thuê/tháng"
    );
    return;
  }

  const submitBtn = document.getElementById("contractSubmitBtn");
  const submitText = document.getElementById("contractSubmitText");

  try {
    if (submitBtn) submitBtn.disabled = true;
    if (submitText) submitText.textContent = "Đang tạo...";

    const res = await API.post("/contracts/from-reservation", {
      room_id: roomId,
      start_date: startDate,
      end_date: endDate,
      monthly_rent: monthlyRent,
      deposit_amount: depositAmount,
      payment_day: paymentDay,
      notes,
    });

    if (!res.ok) {
      showContractFormError(res.data?.message || "Không thể tạo hợp đồng");
      return;
    }

    closeContractModal();
    await loadRooms();
    alert("Tạo hợp đồng thành công!");
  } catch (err) {
    console.error("Create contract error:", err);
    showContractFormError("Lỗi kết nối server!");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (submitText) submitText.textContent = "Tạo hợp đồng";
  }
}

async function handleSubmit(e) {
  e.preventDefault();

  const roomId = document.getElementById("roomId")?.value || "";
  const isEdit = !!roomId;

  // Get form values
  const name = document.getElementById("roomName")?.value?.trim();
  const roomType = document.getElementById("roomType")?.value;
  const price = document.getElementById("roomPrice")?.value;

  // Validate required fields (matches backend: name, price, room_type)
  if (!name || !roomType || !price) {
    showFormError("Vui lòng điền đầy đủ: Tên phòng, Loại phòng, Giá thuê");
    return;
  }

  // Build data object matching backend schema
  // Get amenities from checkboxes
  const amenities = Array.from(document.querySelectorAll('input[name="amenities"]:checked')).map(cb => cb.value);

  const data = {
    name: name,
    room_type: roomType,
    price: parseFloat(price),
    electricity_price:
      parseFloat(document.getElementById("electricPrice")?.value) || 3500,
    water_price:
      parseFloat(document.getElementById("waterPrice")?.value) || 15000,
    deposit: parseFloat(document.getElementById("roomDeposit")?.value) || 0,
    area: parseFloat(document.getElementById("roomArea")?.value) || 0,
    floor: parseInt(document.getElementById("roomFloor")?.value) || 1,
    amenities: amenities,
    description:
      document.getElementById("roomDescription")?.value?.trim() || "",
  };

  const imagesInput = document.getElementById("roomImages");
  if (imagesInput && imagesInput.files && imagesInput.files.length > 0) {
    try {
      data.images = await Promise.all(
        Array.from(imagesInput.files).map(fileToImagePayload)
      );
    } catch (err) {
      console.error("Image encode error:", err);
      showFormError("Không thể đọc hình ảnh. Vui lòng thử ảnh khác!");
      return;
    }
  }

  console.log("Submitting room data:", data);

  try {
    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    document.getElementById("submitText").textContent = isEdit
      ? "Đang cập nhật..."
      : "Đang thêm...";

    let res;
    if (isEdit) {
      res = await API.put(`/rooms/${roomId}`, data);
    } else {
      res = await API.post("/rooms", data);
    }

    console.log("API response:", res);

    if (res.ok) {
      closeModal();
      loadRooms();
      alert(isEdit ? "Cập nhật phòng thành công!" : "Thêm phòng thành công!");
    } else {
      showFormError(res.data?.message || "Có lỗi xảy ra!");
    }
  } catch (error) {
    console.error("Submit error:", error);
    showFormError("Lỗi kết nối server!");
  } finally {
    document.getElementById("submitBtn").disabled = false;
    document.getElementById("submitText").textContent = isEdit
      ? "Cập nhật"
      : "Thêm phòng";
  }
}

function fileToImagePayload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      // result: data:<mime>;base64,<data>
      const parts = result.split(",");
      if (parts.length < 2) return reject(new Error("Invalid data URL"));
      const header = parts[0];
      const dataB64 = parts[1];
      const match = header.match(/data:(.*?);base64/i);
      const contentType = match ? match[1] : file.type || "image/jpeg";
      resolve({
        filename: file.name || "",
        content_type: contentType,
        data_b64: dataB64,
      });
    };
    reader.onerror = () =>
      reject(reader.error || new Error("FileReader error"));
    reader.readAsDataURL(file);
  });
}

function showFormError(message) {
  const errorDiv = document.getElementById("formError");
  if (errorDiv) {
    errorDiv.textContent = message;
    errorDiv.classList.remove("hidden");
  }
}

// ============== DELETE MODAL ==============
function openDeleteModal(roomId, roomName) {
  deleteRoomId = roomId;
  document.getElementById("deleteRoomName").textContent = roomName;
  const modal = document.getElementById("deleteModal");
  if (modal) {
    modal.classList.add("active");
    modal.style.display = "flex";
  }
}

function closeDeleteModal() {
  deleteRoomId = null;
  const modal = document.getElementById("deleteModal");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none";
  }
}

async function confirmDelete() {
  if (!deleteRoomId) return;

  try {
    const res = await API.delete(`/rooms/${deleteRoomId}`);
    if (res.ok) {
      closeDeleteModal();
      loadRooms();
      alert("Xóa phòng thành công!");
    } else {
      alert(res.data?.message || "Không thể xóa phòng!");
    }
  } catch (error) {
    console.error("Delete error:", error);
    alert("Lỗi kết nối server!");
  }
}
