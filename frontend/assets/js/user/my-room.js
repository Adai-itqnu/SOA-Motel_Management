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
    // Check for reserved rooms first (bookings with deposit_paid but no contract yet)
    const hasReserved = await checkAndShowReservedRooms();
    
    // If we have reserved rooms, ONLY show those - don't show active contracts
    if (hasReserved) {
      return;
    }
    
    // No reserved rooms, check for active contracts
    const contractRes = await API.get("/contracts");
    if (contractRes.ok) {
      const contracts = contractRes.data?.contracts || [];
      const activeContract = contracts.find((c) => c.status === "active");

      if (activeContract) {
        currentContract = activeContract;
        
        const roomRes = await API.get("/rooms/" + activeContract.room_id);
        if (roomRes.ok && roomRes.data) {
          displayRoomInfo(roomRes.data);
        }

        displayContractInfo(activeContract);
        await loadPaymentHistory();
        showRoomContent();
        return;
      }
    }
    
    // No reserved and no active contract
    showNoRoom();
  } catch (error) {
    console.error("Load my room error:", error);
    showNoRoom();
  }
}

async function checkAndShowReservedRooms() {
  try {
    // Get bookings with deposit_paid (not yet checked in)
    const bookingsRes = await API.get("/bookings");
    if (!bookingsRes.ok) return false;
    
    const bookings = bookingsRes.data?.bookings || [];
    const pendingCheckIn = bookings.filter(
      (b) => b.status === "deposit_paid" || 
            (b.deposit_status === "paid" && b.status !== "checked_in")
    );

    if (pendingCheckIn.length === 0) return false;

    // Get contracts to exclude rooms that already have active contracts
    const contractsRes = await API.get("/contracts");
    const contracts = contractsRes.ok ? (contractsRes.data?.contracts || []) : [];
    const activeContractRoomIds = contracts
      .filter(c => c.status === "active")
      .map(c => c.room_id);
    
    // Filter out rooms with active contracts
    const reservedBookings = pendingCheckIn.filter(
      b => !activeContractRoomIds.includes(b.room_id)
    );

    if (reservedBookings.length === 0) return false;

    await showReservedSectionFromBookings(reservedBookings);
    return true;
  } catch (error) {
    console.error("Check reserved rooms error:", error);
  }
  
  // Fallback: if no bookings found, check for completed payments
  try {
    const paymentRes = await API.get("/payments");
    if (paymentRes.ok) {
      const payments = paymentRes.data?.payments || [];
      const depositPayments = payments.filter(
        (p) =>
          p.payment_type === "room_reservation_deposit" &&
          p.status === "completed"
      );

      if (depositPayments.length > 0) {
        await showReservedSection(depositPayments);
        return true;
      }
    }
  } catch (error) {
    console.error("Check payments fallback error:", error);
  }
  
  return false;
}

async function checkReservedRoom() {
  try {
    // First check for bookings with deposit_paid status (not yet checked in)
    const bookingsRes = await API.get("/bookings");
    if (bookingsRes.ok) {
      const bookings = bookingsRes.data?.bookings || [];
      const pendingCheckIn = bookings.filter(
        (b) => b.status === "deposit_paid" || 
              (b.deposit_status === "paid" && b.status !== "checked_in")
      );

      if (pendingCheckIn.length > 0) {
        await showReservedSectionFromBookings(pendingCheckIn);
        return;
      }
    }

    // Fallback: check payments for room reservation deposits
    const paymentRes = await API.get("/payments");
    if (paymentRes.ok) {
      const payments = paymentRes.data?.payments || [];
      const depositPayments = payments.filter(
        (p) =>
          p.payment_type === "room_reservation_deposit" &&
          p.status === "completed"
      );

      if (depositPayments.length > 0) {
        await showReservedSection(depositPayments);
        return;
      }
    }
  } catch (error) {
    console.error("Check reserved room error:", error);
  }
  showNoRoom();
}

async function showReservedSectionFromBookings(bookings) {
  const section = document.getElementById("reservedSection");
  const list = document.getElementById("reservedRoomsList");
  
  if (!section || !list) {
    showNoRoom();
    return;
  }

  const cards = [];
  for (const booking of bookings) {
    if (!booking.room_id) continue;
    const roomRes = await API.get("/rooms/" + booking.room_id);
    if (!roomRes.ok || !roomRes.data) continue;
    
    const room = roomRes.data;
    // Convert booking to payment-like object for card rendering
    const paymentLike = {
      _id: booking._id,
      room_id: booking.room_id,
      check_in_date: booking.check_in_date,
      amount: booking.deposit_amount || 0
    };
    const card = buildReservedRoomCard(room, paymentLike);
    cards.push(card);
  }

  if (cards.length === 0) {
    showNoRoom();
    return;
  }

  list.innerHTML = cards.join("");
  
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("noRoom").classList.add("hidden");
  document.getElementById("roomContent").classList.add("hidden");
  section.classList.remove("hidden");
}

async function showReservedSection(depositPayments) {
  const section = document.getElementById("reservedSection");
  const list = document.getElementById("reservedRoomsList");
  
  if (!section || !list) {
    // Fall back to old single-room behavior
    const firstPayment = depositPayments[0];
    if (firstPayment && firstPayment.room_id) {
      const roomRes = await API.get("/rooms/" + firstPayment.room_id);
      if (roomRes.ok && roomRes.data) {
        displayRoomInfo(roomRes.data);
        const statusEl = document.getElementById("roomStatusText");
        if (statusEl) statusEl.textContent = "Đã đặt cọc";
        showWaitingContract(firstPayment);
        await loadPaymentHistory();
        showRoomContent();
        return;
      }
    }
    showNoRoom();
    return;
  }

  // Build cards for each reserved room
  const cards = [];
  for (const payment of depositPayments) {
    if (!payment.room_id) continue;
    const roomRes = await API.get("/rooms/" + payment.room_id);
    if (!roomRes.ok || !roomRes.data) continue;
    
    const room = roomRes.data;
    const card = buildReservedRoomCard(room, payment);
    cards.push(card);
  }

  if (cards.length === 0) {
    showNoRoom();
    return;
  }

  list.innerHTML = cards.join("");
  
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("noRoom").classList.add("hidden");
  document.getElementById("roomContent").classList.add("hidden");
  section.classList.remove("hidden");
}

function buildReservedRoomCard(room, payment) {
  let canCheckIn = false;
  let checkInDateText = "";
  if (payment && payment.check_in_date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const checkInDate = new Date(payment.check_in_date);
    checkInDate.setHours(0, 0, 0, 0);
    canCheckIn = today >= checkInDate;
    checkInDateText = formatDate(payment.check_in_date);
  } else {
    canCheckIn = true;
  }

  // Get room image - handle base64 format
  let roomImage = "/assets/images/room-placeholder.svg";
  if (room.images && room.images.length > 0) {
    const firstImg = room.images[0];
    if (typeof firstImg === 'string') {
      roomImage = firstImg;
    } else if (firstImg && firstImg.data_b64) {
      roomImage = `data:${firstImg.content_type || 'image/jpeg'};base64,${firstImg.data_b64}`;
    }
  }

  const roomName = room.code || room.name || room._id;
  const roomPrice = formatCurrency(room.price || 0);
  const depositAmount = formatCurrency(payment.amount || 0);
  const paymentId = payment._id || "";
  const roomId = payment.room_id || "";
  const checkInDateVal = payment.check_in_date || "";

  // Lock overlay for rooms not at check-in date
  const lockOverlay = !canCheckIn ? `
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-10">
      <div class="text-center text-white">
        <span class="material-symbols-outlined text-5xl">lock</span>
        <p class="text-sm mt-2 font-medium">Chờ đến ngày check-in</p>
        <p class="text-xs opacity-80">${checkInDateText}</p>
      </div>
    </div>
  ` : '';

  const button = canCheckIn
    ? `<button onclick="confirmCheckInFor('${paymentId}', '${roomId}', '${checkInDateVal}')"
         class="w-full py-3 bg-primary hover:bg-red-700 text-white rounded-xl font-bold text-sm transition shadow-lg">
         <span class="flex items-center justify-center gap-2">
           <span class="material-symbols-outlined text-lg">door_open</span>
           Xác nhận nhận phòng
         </span>
       </button>`
    : `<div class="w-full py-3 bg-gray-200 text-gray-400 rounded-xl text-center text-sm font-medium cursor-not-allowed">
         <span class="flex items-center justify-center gap-2">
           <span class="material-symbols-outlined text-lg">lock</span>
           Chờ đến ngày ${checkInDateText}
         </span>
       </div>`;

  return `
    <div class="bg-white rounded-2xl shadow-card overflow-hidden border border-gray-100 relative ${!canCheckIn ? 'opacity-95' : ''}">
      <div class="relative h-48">
        <img src="${roomImage}" alt="${roomName}" class="w-full h-full object-cover" 
             onerror="this.src='/assets/images/room-placeholder.svg'" />
        ${lockOverlay}
        <div class="absolute top-3 right-3 z-20">
          <span class="px-3 py-1.5 ${canCheckIn ? 'bg-green-500' : 'bg-amber-500'} text-white text-xs font-bold rounded-full">
            ${canCheckIn ? 'Sẵn sàng nhận phòng' : 'Chờ nhận phòng'}
          </span>
        </div>
      </div>
      <div class="p-5 space-y-4">
        <div>
          <h3 class="text-lg font-bold text-gray-900">${roomName}</h3>
          <p class="text-sm text-gray-500">${room.room_type ? getRoomTypeLabel(room.room_type) : ''} ${room.area ? '• ' + room.area + ' m²' : ''}</p>
        </div>
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div class="bg-gray-50 rounded-lg p-3">
            <p class="text-gray-500">Giá thuê</p>
            <p class="font-bold text-gray-900">${roomPrice}</p>
          </div>
          <div class="bg-primary/5 rounded-lg p-3">
            <p class="text-gray-500">Đã cọc</p>
            <p class="font-bold text-primary">${depositAmount}</p>
          </div>
        </div>
        ${checkInDateText ? `<div class="text-sm text-gray-600 flex items-center gap-2">
          <span class="material-symbols-outlined text-sm">calendar_month</span>
          Ngày check-in: <strong>${checkInDateText}</strong>
        </div>` : ''}
        ${button}
      </div>
    </div>
  `;
}

async function confirmCheckInFor(paymentId, roomId, checkInDate) {
  const btn = event.target;
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Đang xử lý...";

  try {
    // Try to find a booking first
    const bookingsRes = await API.get("/bookings");
    if (bookingsRes.ok) {
      const bookings = bookingsRes.data?.bookings || [];
      const booking = bookings.find(
        (b) => b.room_id === roomId &&
              (b.deposit_status === "paid" || b.status === "deposit_paid")
      );

      if (booking) {
        btn.textContent = "Đang tạo hợp đồng...";
        const checkInRes = await API.post(`/bookings/${booking._id}/check-in`);
        if (checkInRes.ok) {
          alert("Nhận phòng thành công! Hợp đồng đã được tạo.");
          window.location.reload();
          return;
        } else {
          alert(checkInRes.data?.message || "Không thể xác nhận nhận phòng.");
          btn.disabled = false;
          btn.textContent = originalText;
          return;
        }
      }
    }

    // No booking found, try check-in from payment
    btn.textContent = "Đang tạo hợp đồng...";
    const checkInRes = await API.post("/bookings/check-in-from-payment", {
      payment_id: paymentId,
      room_id: roomId,
      check_in_date: checkInDate
    });

    if (checkInRes.ok) {
      alert("Nhận phòng thành công! Hợp đồng đã được tạo.");
      window.location.reload();
    } else {
      alert(checkInRes.data?.message || "Không thể xác nhận nhận phòng.");
      btn.disabled = false;
      btn.textContent = originalText;
    }
  } catch (error) {
    console.error("Check-in error:", error);
    alert("Lỗi kết nối. Vui lòng thử lại.");
    btn.disabled = false;
    btn.textContent = originalText;
  }
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

// Global variable to store current payment for check-in
let currentDepositPayment = null;

function showWaitingContract(payment = null) {
  currentDepositPayment = payment;
  const contractInfo = document.getElementById("contractInfo");
  
  // Check if today >= check_in_date
  let canCheckIn = false;
  let checkInDateText = "";
  if (payment && payment.check_in_date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const checkInDate = new Date(payment.check_in_date);
    checkInDate.setHours(0, 0, 0, 0);
    canCheckIn = today >= checkInDate;
    checkInDateText = formatDate(payment.check_in_date);
  }
  
  contractInfo.innerHTML = `
    <div class="text-center py-6">
      <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <span class="material-symbols-outlined text-2xl text-amber-600">${canCheckIn ? 'check_circle' : 'schedule'}</span>
      </div>
      <p class="text-amber-700 font-medium">${canCheckIn ? 'Sẵn sàng nhận phòng' : 'Đang chờ nhận phòng'}</p>
      ${checkInDateText ? `<p class="text-gray-600 text-sm mt-1">Ngày check-in: <strong>${checkInDateText}</strong></p>` : ''}
      ${canCheckIn 
        ? `<p class="text-gray-500 text-sm mt-1 mb-4">Hệ thống sẽ tự động tạo hợp đồng khi bạn xác nhận.</p>
           <button id="checkInBtn" onclick="confirmCheckIn()" class="w-full py-3 px-4 rounded-lg bg-primary hover:bg-red-700 text-white font-bold text-sm shadow-lg transition active:scale-[0.98]">
             <span id="checkInBtnText">Xác nhận nhận phòng</span>
           </button>`
        : `<p class="text-gray-500 text-sm mt-1">Vui lòng quay lại vào ngày check-in để nhận phòng và tạo hợp đồng.</p>`
      }
    </div>
  `;
  
  const statusEl = document.getElementById("contractStatusBadge");
  if (canCheckIn) {
    statusEl.textContent = "Sẵn sàng nhận";
    statusEl.className = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200";
  } else {
    statusEl.textContent = "Chờ nhận phòng";
    statusEl.className = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 border border-amber-200";
  }
}

async function confirmCheckIn() {
  if (!currentDepositPayment) {
    alert("Không tìm thấy thông tin đặt cọc!");
    return;
  }
  
  const btn = document.getElementById("checkInBtn");
  const btnText = document.getElementById("checkInBtnText");
  
  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = "Đang xử lý...";
  
  try {
    // Find the booking associated with this payment
    const bookingsRes = await API.get("/bookings");
    if (!bookingsRes.ok) {
      alert("Không thể tải thông tin đặt phòng!");
      resetCheckInBtn();
      return;
    }
    
    const bookings = bookingsRes.data?.bookings || [];
    // Find booking with matching room_id and deposit_paid status
    const booking = bookings.find(
      (b) => b.room_id === currentDepositPayment.room_id && 
             (b.deposit_status === "paid" || b.status === "deposit_paid")
    );
    
    if (!booking) {
      // If no booking found, try to create contract directly via room reservation
      if (btnText) btnText.textContent = "Đang tạo hợp đồng...";
      
      const checkInRes = await API.post("/bookings/check-in-from-payment", {
        payment_id: currentDepositPayment._id,
        room_id: currentDepositPayment.room_id,
        check_in_date: currentDepositPayment.check_in_date
      });
      
      if (checkInRes.ok) {
        alert("Nhận phòng thành công! Hợp đồng đã được tạo.");
        window.location.reload();
        return;
      } else {
        alert(checkInRes.data?.message || "Không thể xác nhận nhận phòng. Vui lòng liên hệ quản lý.");
        resetCheckInBtn();
        return;
      }
    }
    
    // Call check-in API
    if (btnText) btnText.textContent = "Đang tạo hợp đồng...";
    const checkInRes = await API.post(`/bookings/${booking._id}/check-in`);
    
    if (checkInRes.ok) {
      alert("Nhận phòng thành công! Hợp đồng đã được tạo.");
      window.location.reload();
    } else {
      alert(checkInRes.data?.message || "Không thể xác nhận nhận phòng. Vui lòng thử lại.");
      resetCheckInBtn();
    }
  } catch (error) {
    console.error("Check-in error:", error);
    alert("Lỗi kết nối server. Vui lòng thử lại.");
    resetCheckInBtn();
  }
}

function resetCheckInBtn() {
  const btn = document.getElementById("checkInBtn");
  const btnText = document.getElementById("checkInBtnText");
  if (btn) btn.disabled = false;
  if (btnText) btnText.textContent = "Xác nhận nhận phòng";
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
  if (!currentContract) {
    alert("Bạn cần có phòng đang thuê để báo cáo sự cố.");
    return;
  }
  
  // Get room name from page title or contract
  const pageTitle = document.getElementById("pageTitle");
  const roomName = pageTitle ? pageTitle.textContent : (currentContract.room_code || "Phòng của tôi");
  
  // Display room info in modal
  const reportRoomName = document.getElementById("reportRoomName");
  if (reportRoomName) {
    reportRoomName.textContent = roomName;
  }
  
  // Reset form
  document.getElementById("reportForm").reset();
  document.getElementById("reportError").classList.add("hidden");
  
  // Show modal
  document.getElementById("reportModal").classList.remove("hidden");
}

function closeReportModal() {
  document.getElementById("reportModal").classList.add("hidden");
}

// Handle report form submission
document.addEventListener("DOMContentLoaded", () => {
  const reportForm = document.getElementById("reportForm");
  if (reportForm) {
    reportForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await submitIncidentReport();
    });
  }
});

async function submitIncidentReport() {
  const issueType = document.getElementById("reportIssueType").value;
  const content = document.getElementById("reportContent").value.trim();
  const submitBtn = document.getElementById("reportSubmitBtn");
  const errorEl = document.getElementById("reportError");
  
  if (!issueType || !content) {
    errorEl.textContent = "Vui lòng chọn loại sự cố và mô tả chi tiết.";
    errorEl.classList.remove("hidden");
    return;
  }
  
  // Get user info
  const user = Auth.getUser();
  const userName = user?.fullname || user?.username || "Người dùng";
  const userId = user?._id || user?.id;
  
  // Get room info
  const roomName = document.getElementById("reportRoomName")?.textContent || "Không xác định";
  const roomId = currentContract?.room_id || "";
  
  // Issue type labels
  const issueLabels = {
    electric: "Điện",
    water: "Nước",
    furniture: "Nội thất",
    security: "An ninh",
    noise: "Tiếng ồn",
    other: "Khác"
  };
  
  const issueLabel = issueLabels[issueType] || issueType;
  
  // Disable button
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="animate-spin">⏳</span> Đang gửi...';
  errorEl.classList.add("hidden");
  
  try {
    // Send report to notification service
    const res = await API.post("/notifications/report-issue", {
      issue_type: issueType,
      issue_label: issueLabel,
      content: content,
      room_id: roomId,
      room_name: roomName,
      user_name: userName,
      user_id: userId
    });
    
    if (res.ok) {
      closeReportModal();
      // Show success toast
      showToast("Đã gửi báo cáo sự cố thành công! Quản lý sẽ xem xét và phản hồi.", "success");
    } else {
      errorEl.textContent = res.data?.message || "Không thể gửi báo cáo. Vui lòng thử lại.";
      errorEl.classList.remove("hidden");
    }
  } catch (error) {
    console.error("Submit report error:", error);
    errorEl.textContent = "Lỗi kết nối. Vui lòng thử lại sau.";
    errorEl.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="material-symbols-outlined text-lg">send</span> Gửi báo cáo';
  }
}

function showToast(message, type = "success") {
  // Remove existing toast
  const existingToast = document.getElementById("toast-notification");
  if (existingToast) existingToast.remove();
  
  const bgColor = type === "success" ? "bg-green-500" : type === "error" ? "bg-red-500" : "bg-blue-500";
  const icon = type === "success" ? "check_circle" : type === "error" ? "error" : "info";
  
  const toast = document.createElement("div");
  toast.id = "toast-notification";
  toast.className = `fixed top-4 right-4 z-[100] flex items-center gap-3 px-5 py-4 ${bgColor} text-white rounded-xl shadow-2xl transform translate-x-full transition-transform duration-300`;
  toast.innerHTML = `
    <span class="material-symbols-outlined">${icon}</span>
    <p class="font-medium">${message}</p>
  `;
  
  document.body.appendChild(toast);
  
  // Animate in
  setTimeout(() => {
    toast.classList.remove("translate-x-full");
  }, 100);
  
  // Auto hide after 5s
  setTimeout(() => {
    toast.classList.add("translate-x-full");
    setTimeout(() => toast.remove(), 300);
  }, 5000);
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

