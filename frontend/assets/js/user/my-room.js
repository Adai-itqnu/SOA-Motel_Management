let currentContract = null;

document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.isLoggedIn()) {
    window.location.href = "/auth/login.html";
    return;
  }
  // Layout.js handles user info and dropdowns
  setLandlordDefault();
  loadMyRoom();
});

function setLandlordDefault() {
  const nameEl = document.getElementById("landlordName");
  const roleEl = document.getElementById("landlordRole");
  const avatarEl = document.getElementById("landlordAvatar");
  if (nameEl) nameEl.textContent = "Admin";
  if (roleEl) roleEl.textContent = "Quản lý tòa nhà";
  if (avatarEl) {
    avatarEl.textContent = "A";
    avatarEl.style.backgroundImage = "";
    avatarEl.classList.add(
      "flex",
      "items-center",
      "justify-center",
      "text-primary",
      "font-bold",
      "bg-primary/10"
    );
  }
}

async function loadMyRoom() {
  try {
    const contractRes = await API.get("/contracts");
    if (!contractRes.ok) {
      showNoRoom();
      return;
    }

    const contracts = contractRes.data?.contracts || [];
    const activeContract = contracts.find((c) => c.status === "active");

    if (!activeContract) {
      await checkReservedRoom();
      return;
    }

    currentContract = activeContract;

    const roomRes = await API.get("/rooms/" + activeContract.room_id);
    if (roomRes.ok && roomRes.data) {
      displayRoomInfo(roomRes.data);
    }

    displayContractInfo(activeContract);
    await loadPaymentHistory();
    showRoomContent();
  } catch (error) {
    console.error("Load my room error:", error);
    showNoRoom();
  }
}

async function checkReservedRoom() {
  try {
    const paymentRes = await API.get("/payments");
    if (paymentRes.ok) {
      const payments = paymentRes.data?.payments || [];
      const depositPayment = payments.find(
        (p) =>
          p.payment_type === "room_reservation_deposit" &&
          p.status === "completed"
      );

      if (depositPayment && depositPayment.room_id) {
        const roomRes = await API.get("/rooms/" + depositPayment.room_id);
        if (roomRes.ok && roomRes.data) {
          displayRoomInfo(roomRes.data);
          // Override room status to show "Đã đặt cọc" since user has paid deposit
          const statusEl = document.getElementById("roomStatusText");
          if (statusEl) {
            statusEl.textContent = "Đã đặt cọc";
          }
          showWaitingContract();
          await loadPaymentHistory();
          showRoomContent();
          return;
        }
      }
    }
  } catch (error) {
    console.error("Check reserved room error:", error);
  }
  showNoRoom();
}

function displayRoomInfo(room) {
  const firstImage = room.images?.[0] || "/assets/images/room-placeholder.svg";
  document.getElementById("roomImage").src = firstImage;
  document.getElementById("pageTitle").textContent =
    (room.code || room.name || "Phòng của tôi") +
    (room.room_type ? " - " + getRoomTypeLabel(room.room_type) : "");
  document.getElementById("roomPrice").textContent = formatNumber(
    room.price || 0
  );
  document.getElementById("roomArea").textContent = room.area || "--";
  document.getElementById("roomFloorInfo").textContent =
    "Tầng " + (room.floor || "--");
  document.getElementById("roomBeds").textContent = room.bedrooms || "--";
  document.getElementById("roomDescription").textContent =
    room.name || "Căn hộ dịch vụ";

  const statusLabels = {
    available: "Còn trống",
    reserved: "Đã đặt cọc",
    occupied: "Đang ở",
  };
  document.getElementById("roomStatusText").textContent =
    statusLabels[room.status] || room.status;

  const amenities = room.amenities || [];
  const amenityIcons = {
    wifi: "wifi",
    air_conditioner: "ac_unit",
    water_heater: "water_heater",
    washing_machine: "local_laundry_service",
    fridge: "kitchen",
    kitchen: "restaurant_menu",
    private_wc: "bathtub",
    balcony: "deck",
    parking: "two_wheeler",
    security: "shield",
    elevator: "elevator",
    furniture: "weekend",
    bed: "king_bed",
  };
  const amenityLabels = {
    wifi: "WiFi tốc độ cao",
    air_conditioner: "Điều hòa",
    water_heater: "Nóng lạnh",
    washing_machine: "Máy giặt chung",
    fridge: "Tủ lạnh",
    kitchen: "Bếp",
    private_wc: "WC riêng",
    balcony: "Ban công",
    parking: "Để xe",
    security: "Bảo vệ",
    elevator: "Thang máy",
    furniture: "Nội thất",
    bed: "Giường",
  };

  document.getElementById("amenitiesList").innerHTML =
    amenities.length > 0
      ? amenities
          .map((a) => {
            const icon = amenityIcons[a] || "check_circle";
            const label = amenityLabels[a] || a;
            return `<div class="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg text-sm text-gray-700">
                        <span class="material-symbols-outlined text-[18px] text-gray-500">${icon}</span> ${label}
                    </div>`;
          })
          .join("")
      : '<span class="text-gray-500 text-sm">Không có thông tin</span>';
}

function displayContractInfo(contract) {
  const statusLabels = {
    active: "Đang hiệu lực",
    terminated: "Đã kết thúc",
    expired: "Hết hạn",
  };
  const statusEl = document.getElementById("contractStatusBadge");
  statusEl.textContent = statusLabels[contract.status] || contract.status;
  if (contract.status === "active") {
    statusEl.className =
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200";
  } else {
    statusEl.className =
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200";
  }

  document.getElementById("contractStart").textContent = formatDate(
    contract.start_date
  );
  document.getElementById("contractEnd").textContent = formatDate(
    contract.end_date
  );
  document.getElementById("contractPayDay").textContent =
    "Ngày " + (contract.payment_day || 5) + " hàng tháng";
  document.getElementById("contractDeposit").textContent = formatCurrency(
    contract.deposit_amount || 0
  );

  currentContract = contract;
}

function showWaitingContract() {
  const contractInfo = document.getElementById("contractInfo");
  contractInfo.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <span class="material-symbols-outlined text-2xl text-amber-600">schedule</span>
                    </div>
                    <p class="text-amber-700 font-medium">Đang chờ tạo hợp đồng</p>
                    <p class="text-gray-500 text-sm mt-1">Bạn đã đặt cọc thành công. Vui lòng đợi quản lý liên hệ để hoàn tất hợp đồng.</p>
                </div>
            `;
  const statusEl = document.getElementById("contractStatusBadge");
  statusEl.textContent = "Chờ hợp đồng";
  statusEl.className =
    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 border border-amber-200";
}

async function loadPaymentHistory() {
  try {
    const res = await API.get("/payments");
    if (!res.ok) return;

    const payments = res.data?.payments || [];

    const typeLabels = {
      room_reservation_deposit: "Đặt cọc phòng",
      booking_deposit: "Đặt cọc",
      monthly_rent: "Tiền thuê tháng",
      bill: "Hóa đơn",
      bill_payment: "Thanh toán hóa đơn",
    };

    const paymentsList = document.getElementById("paymentsList");
    if (payments.length === 0) {
      paymentsList.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500">Chưa có lịch sử thanh toán</td></tr>`;
      return;
    }

    paymentsList.innerHTML = payments
      .slice(0, 5)
      .map((p) => {
        let statusBg = "bg-orange-100 text-orange-800";
        let statusText = "Đang chờ";
        if (p.status === "completed") {
          statusBg = "bg-green-100 text-green-800";
          statusText = "Đã thanh toán";
        } else if (p.status === "failed") {
          statusBg = "bg-red-100 text-red-800";
          statusText = "Thất bại";
        }

        return `<tr class="group hover:bg-gray-50 transition-colors">
                        <td class="px-6 py-4 font-semibold">${formatDate(
                          p.created_at
                        )}</td>
                        <td class="px-6 py-4 text-gray-600">${
                          typeLabels[p.payment_type] ||
                          p.payment_type ||
                          "Thanh toán"
                        }</td>
                        <td class="px-6 py-4 font-bold text-primary">${formatCurrency(
                          p.amount || 0
                        )}</td>
                        <td class="px-6 py-4 text-gray-500">${formatDate(
                          p.due_date || p.created_at
                        )}</td>
                        <td class="px-6 py-4 text-right"><span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBg}">${statusText}</span></td>
                    </tr>`;
      })
      .join("");
  } catch (error) {
    console.error("Load payments error:", error);
  }
}

function showNoRoom() {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("noRoom").classList.remove("hidden");
}

function showRoomContent() {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("roomContent").classList.remove("hidden");
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

function formatCurrency(amount) {
  return new Intl.NumberFormat("vi-VN").format(amount || 0) + " đ";
}

function formatNumber(num) {
  return new Intl.NumberFormat("vi-VN").format(num || 0);
}

function formatDate(dateStr) {
  if (!dateStr) return "--";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function reportIssue() {
  alert("Chức năng báo cáo sự cố đang phát triển.");
}

function openPaymentModal() {
  if (!currentContract) {
    alert("Chưa có hợp đồng để thanh toán.");
    return;
  }
  alert("Chuyển hướng đến trang thanh toán...");
  window.location.href = "/user/bills.html";
}

function downloadContract() {
  if (!currentContract) {
    alert("Chưa có hợp đồng để tải xuống.");
    return;
  }
  alert("Tính năng tải hợp đồng đang phát triển.");
}

function callLandlord() {
  alert("Tính năng gọi điện đang phát triển.");
}

function messageLandlord() {
  alert("Tính năng nhắn tin đang phát triển.");
}

function logout() {
  Auth.logout();
  window.location.href = "/auth/login.html";
}
