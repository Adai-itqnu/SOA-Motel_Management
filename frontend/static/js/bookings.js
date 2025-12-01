(function () {
  let allBookings = [];

  window.loadBookingsData = async function loadBookingsData() {
    console.log("loadBookingsData called");
    try {
      const headers = getAuthHeader();
      const response = await fetch(buildApiUrl("/api/bookings"), { headers });
      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!response.ok) throw new Error("Không thể tải danh sách bookings");
      const data = await response.json();
      allBookings = data.bookings || [];
      filterBookings();
    } catch (error) {
      console.error("Error loading bookings:", error);
    }
  };

  window.approveBooking = async function approveBooking(bookingId) {
    if (!confirm("Bạn có chắc muốn duyệt booking này?")) return;
    try {
      const response = await fetch(
        buildApiUrl(`/api/bookings/${bookingId}/approve`),
        {
          method: "PUT",
          headers: getAuthHeader(),
        }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      alert(data.message);
      loadBookingsData();
      // Reload contracts and rooms to update status if available
      if (typeof loadContractsData === "function") {
        loadContractsData();
      }
      if (typeof loadRoomsData === "function") {
        loadRoomsData();
      }
    } catch (error) {
      alert(error.message);
    }
  };



  window.rejectBooking = async function rejectBooking(bookingId) {
    const reason = prompt("Nhập lý do từ chối (tùy chọn):");
    try {
      const response = await fetch(
        buildApiUrl(`/api/bookings/${bookingId}/reject`),
        {
          method: "PUT",
          headers: {
            ...getAuthHeader(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ reason: reason || "" }),
        }
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.message);
      alert(data.message);
      loadBookingsData();
    } catch (error) {
      alert(error.message);
    }
  };

  window.viewBooking = async function viewBooking(bookingId) {
    try {
      const booking = allBookings.find((b) => b._id === bookingId);
      if (!booking) {
        alert("Không tìm thấy booking");
        return;
      }
      const info = `
Thông tin booking:
Mã: ${booking._id}
Người thuê: ${booking.tenant_info?.name || "-"}
SĐT: ${booking.tenant_info?.phone || "-"}
Phòng: ${booking.room_info?.name || booking.room_id}
Từ: ${formatDate(booking.start_date)} đến ${formatDate(booking.end_date)}
Giá thuê: ${formatPrice(booking.monthly_rent)}/tháng
Tiền cọc: ${formatPrice(booking.deposit)}
Trạng thái: ${booking.status === "pending"
          ? "Đang chờ duyệt"
          : booking.status === "approved"
            ? "Đã duyệt"
            : booking.status === "rejected"
              ? "Đã từ chối"
              : "Đã hủy"
        }
${booking.notes ? `Ghi chú: ${booking.notes}` : ""}
    `;
      alert(info);
    } catch (error) {
      alert(error.message);
    }
  };

  function filterBookings() {
    const searchInput = document.getElementById("bookingSearchInput");
    const statusFilter = document.getElementById("bookingStatusFilter");

    if (!searchInput || !statusFilter) return;

    const searchText = searchInput.value.toLowerCase();
    const statusFilterValue = statusFilter.value;

    let filtered = allBookings.filter((booking) => {
      const matchSearch =
        booking._id?.toLowerCase().includes(searchText) ||
        booking.tenant_info?.name?.toLowerCase().includes(searchText) ||
        booking.room_info?.name?.toLowerCase().includes(searchText);
      const matchStatus =
        !statusFilterValue || booking.status === statusFilterValue;
      return matchSearch && matchStatus;
    });

    renderBookings(filtered);
  }

  function renderBookings(bookings) {
    const tbody = document.getElementById("bookingsTableBody");
    if (!tbody) return;

    if (bookings.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="10" style="text-align: center;">Không tìm thấy booking nào</td></tr>';
      return;
    }

    tbody.innerHTML = bookings
      .map((booking) => {
        const statusClass = `status-${booking.status}`;
        const statusText =
          {
            pending: "Đang chờ duyệt",
            approved: "Đã duyệt",
            rejected: "Đã từ chối",
            cancelled: "Đã hủy",
          }[booking.status] || booking.status;
        return `
        <tr>
            <td>${booking._id}</td>
            <td>${booking.tenant_info?.name || "-"}</td>
            <td>${booking.room_info?.name || booking.room_id || "-"}</td>
            <td>${formatDate(booking.start_date)}</td>
            <td>${formatDate(booking.end_date)}</td>
            <td>${formatPrice(booking.monthly_rent)}</td>
            <td>${formatPrice(booking.deposit)}</td>
            <td>
                <span class="status-badge ${booking.deposit_status === 'paid' ? 'status-approved' : 'status-pending'}">
                    ${booking.deposit_status === 'paid' ? 'Đã thanh toán' : 'Chưa thanh toán'}
                </span>
            </td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                ${booking.status === "pending"
            ? `
                    <button class="btn-action btn-edit" onclick="approveBooking('${booking._id}')">Duyệt</button>
                    <button class="btn-action btn-delete" onclick="rejectBooking('${booking._id}')">Từ chối</button>
                    `
            : `<button class="btn-action btn-view" onclick="viewBooking('${booking._id}')">Xem</button>`
          }
            </td>
        </tr>
    `;
      })
      .join("");
  }

  function initializeBookingsHandlers() {
    console.log("initializeBookingsHandlers called");
    const bookingSearchInput = document.getElementById("bookingSearchInput");
    const bookingStatusFilter = document.getElementById("bookingStatusFilter");

    if (bookingSearchInput && !bookingSearchInput.dataset.initialized) {
      bookingSearchInput.dataset.initialized = "true";
      bookingSearchInput.addEventListener("input", filterBookings);
    }
    if (bookingStatusFilter && !bookingStatusFilter.dataset.initialized) {
      bookingStatusFilter.dataset.initialized = "true";
      bookingStatusFilter.addEventListener("change", filterBookings);
    }
  }

  // Initialize on DOM ready
  document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("bookingsPanel")) {
      initializeBookingsHandlers();
    }
  });

  // Notify that bookings.js is ready
  if (typeof window.scriptsLoaded === "undefined") {
    window.scriptsLoaded = {};
  }
  window.scriptsLoaded.bookings = true;
  console.log("bookings.js loaded");
})();
