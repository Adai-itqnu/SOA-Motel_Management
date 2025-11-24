let allRooms = [];
let currentEditId = null;

// Load room stats
async function loadRoomStats() {
  try {
    const headers = getAuthHeader();
    const response = await fetch("/api/rooms/stats", {
      headers,
    });
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải thống kê");
    const data = await response.json();

    const totalRoomsEl = document.getElementById("roomTotalRooms");
    const availableRoomsEl = document.getElementById("roomAvailableRooms");
    const occupiedRoomsEl = document.getElementById("roomOccupiedRooms");
    const occupancyRateEl = document.getElementById("roomOccupancyRate");

    if (totalRoomsEl) totalRoomsEl.textContent = data.total;
    if (availableRoomsEl) availableRoomsEl.textContent = data.available;
    if (occupiedRoomsEl) occupiedRoomsEl.textContent = data.occupied;
    if (occupancyRateEl)
      occupancyRateEl.textContent = data.occupancy_rate + "%";
  } catch (error) {
    console.error("Error loading room stats:", error);
  }
}

// Load rooms data
window.loadRoomsData = async function loadRoomsData() {
  try {
    const headers = getAuthHeader();
    const response = await fetch("/api/rooms", {
      headers,
    });
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách phòng");
    const data = await response.json();
    allRooms = data.rooms;
    filterRooms();
    loadRoomStats();
  } catch (error) {
    console.error("Error loading rooms:", error);
  }
};

// Filter rooms
function filterRooms() {
  const searchInput = document.getElementById("roomSearchInput");
  const statusFilter = document.getElementById("roomStatusFilter");

  if (!searchInput || !statusFilter) return;

  const searchText = searchInput.value.toLowerCase();
  const statusFilterValue = statusFilter.value;

  let filtered = allRooms.filter((room) => {
    const matchSearch = room.name.toLowerCase().includes(searchText);
    const matchStatus = !statusFilterValue || room.status === statusFilterValue;
    return matchSearch && matchStatus;
  });

  renderRooms(filtered);
}

// Render rooms
function renderRooms(rooms) {
  const tbody = document.getElementById("roomsTableBody");
  if (!tbody) return;

  if (rooms.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="6" style="text-align: center;">Không tìm thấy phòng nào</td></tr>';
    return;
  }

  tbody.innerHTML = rooms
    .map((room) => {
      const statusClass = `status-${room.status}`;
      const statusText = {
        available: "Còn trống",
        occupied: "Đã cho thuê",
        maintenance: "Bảo trì",
      }[room.status];
      return `
        <tr>
            <td>${room._id}</td>
            <td><strong>${room.name}</strong></td>
            <td>${room.room_type}</td>
            <td>${formatPrice(room.price)}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                <button class="btn-action btn-edit" onclick="openEditRoomModal('${
                  room._id
                }')">Sửa</button>
                <button class="btn-action btn-delete" onclick="deleteRoom('${
                  room._id
                }')">Xóa</button>
            </td>
        </tr>
    `;
    })
    .join("");
}

// Open create room modal
window.openCreateRoomModal = function openCreateRoomModal() {
  currentEditId = null;
  const modalTitle = document.getElementById("roomModalTitle");
  const roomForm = document.getElementById("roomForm");
  const roomId = document.getElementById("roomId");
  const modalAlert = document.getElementById("roomModalAlert");

  if (modalTitle) modalTitle.textContent = "Thêm phòng mới";
  if (roomForm) roomForm.reset();
  if (roomId) roomId.value = "";
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("roomModal");
  if (modal) modal.style.display = "block";
};

// Open edit room modal
window.openEditRoomModal = function openEditRoomModal(roomId) {
  const room = allRooms.find((r) => r._id === roomId);
  if (!room) return;

  currentEditId = roomId;
  const modalTitle = document.getElementById("roomModalTitle");
  const roomIdInput = document.getElementById("roomId");
  const roomName = document.getElementById("roomName");
  const roomType = document.getElementById("roomType");
  const roomPrice = document.getElementById("roomPrice");
  const roomDeposit = document.getElementById("roomDeposit");
  const roomPaymentDay = document.getElementById("roomPaymentDay");
  const roomElectricPrice = document.getElementById("roomElectricPrice");
  const roomWaterPrice = document.getElementById("roomWaterPrice");
  const roomStatus = document.getElementById("roomStatus");
  const roomDescription = document.getElementById("roomDescription");
  const modalAlert = document.getElementById("roomModalAlert");

  if (modalTitle) modalTitle.textContent = "Chỉnh sửa phòng";
  if (roomIdInput) roomIdInput.value = roomId;
  if (roomName) roomName.value = room.name;
  if (roomType) roomType.value = room.room_type;
  if (roomPrice) roomPrice.value = room.price;
  if (roomDeposit) roomDeposit.value = room.deposit || 0;
  if (roomPaymentDay) roomPaymentDay.value = room.payment_day || 5;
  if (roomElectricPrice) roomElectricPrice.value = room.electric_price || 3500;
  if (roomWaterPrice) roomWaterPrice.value = room.water_price || 20000;
  if (roomStatus) roomStatus.value = room.status;
  if (roomDescription) roomDescription.value = room.description || "";
  if (modalAlert) modalAlert.style.display = "none";

  const modal = document.getElementById("roomModal");
  if (modal) modal.style.display = "block";
};

// Close room modal
window.closeRoomModal = function closeRoomModal() {
  const modal = document.getElementById("roomModal");
  if (modal) modal.style.display = "none";
};

// Delete room
window.deleteRoom = async function deleteRoom(roomId) {
  if (!confirm("Bạn có chắc muốn xóa phòng này?")) return;
  try {
    const response = await fetch(`/api/rooms/${roomId}`, {
      method: "DELETE",
      headers: getAuthHeader(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message);
    alert(data.message);
    loadRoomsData();
  } catch (error) {
    alert(error.message);
  }
};

// Initialize room form
document.addEventListener("DOMContentLoaded", function () {
  const roomForm = document.getElementById("roomForm");
  if (roomForm) {
    roomForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const roomName = document.getElementById("roomName");
      const roomType = document.getElementById("roomType");
      const roomPrice = document.getElementById("roomPrice");
      const roomDeposit = document.getElementById("roomDeposit");
      const roomPaymentDay = document.getElementById("roomPaymentDay");
      const roomElectricPrice = document.getElementById("roomElectricPrice");
      const roomWaterPrice = document.getElementById("roomWaterPrice");
      const roomStatus = document.getElementById("roomStatus");
      const roomDescription = document.getElementById("roomDescription");

      if (!roomName || !roomType || !roomPrice || !roomDeposit) return;

      const formData = {
        name: roomName.value,
        room_type: roomType.value,
        price: parseFloat(roomPrice.value),
        deposit: parseFloat(roomDeposit.value),
        payment_day: roomPaymentDay ? parseInt(roomPaymentDay.value) : 5,
        electric_price: roomElectricPrice
          ? parseFloat(roomElectricPrice.value)
          : 3500,
        water_price: roomWaterPrice ? parseFloat(roomWaterPrice.value) : 20000,
        status: roomStatus ? roomStatus.value : "available",
        description: roomDescription ? roomDescription.value : "",
      };

      const modalAlert = document.getElementById("roomModalAlert");
      try {
        const url = currentEditId
          ? `/api/rooms/${currentEditId}`
          : "/api/rooms";
        const method = currentEditId ? "PUT" : "POST";
        const response = await fetch(url, {
          method: method,
          headers: getAuthHeader(),
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
          closeRoomModal();
          loadRoomsData();
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
  const searchInput = document.getElementById("roomSearchInput");
  const statusFilter = document.getElementById("roomStatusFilter");

  if (searchInput) {
    searchInput.addEventListener("input", filterRooms);
  }
  if (statusFilter) {
    statusFilter.addEventListener("change", filterRooms);
  }

  // Close modal on outside click
  window.onclick = function (event) {
    const modal = document.getElementById("roomModal");
    if (event.target === modal && modal) {
      closeRoomModal();
    }
  };
});

// Notify that rooms.js is ready
if (typeof window.scriptsLoaded === "undefined") {
  window.scriptsLoaded = {};
}
window.scriptsLoaded.rooms = true;
console.log("rooms.js loaded");
