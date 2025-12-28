/**
 * Admin Bookings History
 * - List all bookings (simplified view)
 * - No approval functionality - just display booking info
 */

let allBookings = [];

document.addEventListener("DOMContentLoaded", () => {
  // Init layout (includes auth check)
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  // Wire filter change
  const filter = document.getElementById("statusFilter");
  if (filter) {
    filter.addEventListener("change", renderBookings);
  }

  loadBookings();
});

function logout() {
  Auth.logout();
}

function refreshBookings() {
  loadBookings();
}

function statusBadge(status) {
  switch (status) {
    case "deposit_paid":
      return { label: "Đã đặt cọc", cls: "bg-indigo-100 text-indigo-700" };
    case "approved":
    case "confirmed":
      return { label: "Đã xác nhận", cls: "bg-green-100 text-green-700" };
    case "cancelled":
      return { label: "Đã hủy", cls: "bg-gray-100 text-gray-600" };
    default:
      return { label: status || "--", cls: "bg-gray-100 text-gray-700" };
  }
}

function paymentMethodLabel(method) {
  switch (String(method || "").toLowerCase()) {
    case "vnpay":
      return "VNPay";
    case "cash":
      return "Tiền mặt";
    case "bank_transfer":
      return "Chuyển khoản";
    default:
      return method || "--";
  }
}

async function loadBookings() {
  UI.hide("adminBookingsError");
  UI.hide("adminBookingsSuccess");
  UI.show("adminBookingsLoading");
  UI.hide("adminBookingsEmpty");
  UI.hide("adminBookingsTable");

  const res = await API.get("/bookings");
  UI.hide("adminBookingsLoading");

  if (!res.ok) {
    UI.showError(
      "adminBookingsError",
      res.data?.message || "Không thể tải danh sách đặt phòng"
    );
    return;
  }

  const bookings = res.data?.bookings || [];
  
  // Fetch user and room info for each booking
  allBookings = await Promise.all(
    bookings.map(async (b) => {
      // Get user info
      if (b.user_id && !b.user_name) {
        try {
          const userRes = await API.get(`/users/${b.user_id}`);
          if (userRes.ok && userRes.data) {
            b.user_name = userRes.data.fullName || userRes.data.name || userRes.data.email;
            b.user_phone = userRes.data.phone || "";
            b.user_email = userRes.data.email || "";
          }
        } catch (e) { /* ignore */ }
      }
      // Get room info
      if (b.room_id && !b.room_code) {
        try {
          const roomRes = await API.get(`/rooms/${b.room_id}`);
          if (roomRes.ok && roomRes.data) {
            b.room_code = roomRes.data.name || roomRes.data.code || roomRes.data._id;
          }
        } catch (e) { /* ignore */ }
      }
      return b;
    })
  );
  
  updateStats();
  renderBookings();
}

function updateStats() {
  const total = allBookings.length;
  const pending = allBookings.filter(
    (b) => b.status === "deposit_paid"
  ).length;
  const confirmed = allBookings.filter(
    (b) => b.status === "confirmed" || b.status === "approved"
  ).length;
  const cancelled = allBookings.filter(
    (b) => b.status === "cancelled"
  ).length;

  document.getElementById("statTotal").textContent = total;
  document.getElementById("statPending").textContent = pending;
  document.getElementById("statConfirmed").textContent = confirmed;
  document.getElementById("statCancelled").textContent = cancelled;
}

function renderBookings() {
  const filter = document.getElementById("statusFilter")?.value || "";
  let filtered = allBookings;

  if (filter) {
    filtered = allBookings.filter((b) => b.status === filter);
  }

  if (filtered.length === 0) {
    UI.hide("adminBookingsTable");
    UI.show("adminBookingsEmpty");
    return;
  }

  const list = document.getElementById("adminBookingsList");
  list.innerHTML = filtered.map(renderBookingRow).join("");
  UI.hide("adminBookingsEmpty");
  UI.show("adminBookingsTable");
}

function renderBookingRow(b) {
  const status = statusBadge(b.status);
  const checkIn = (b.check_in_date || "").split("T")[0] || "--";
  const userName = b.user_name || b.user_fullname || b.user_id || "--";
  const roomCode = b.room_code || b.room_name || b.room_id || "--";
  const depositAmount = UI.formatCurrency(b.deposit_amount || 0);
  const paymentMethod = paymentMethodLabel(b.payment_method);

  return `
    <tr class="hover:bg-gray-50 transition-colors">
      <td class="px-6 py-4">
        <div class="font-medium text-gray-900">${escapeHtml(userName)}</div>
        <div class="text-sm text-gray-500">${escapeHtml(
          b.user_phone || b.user_email || ""
        )}</div>
      </td>
      <td class="px-6 py-4">
        <span class="font-medium text-gray-900">${escapeHtml(roomCode)}</span>
      </td>
      <td class="px-6 py-4">
        <span class="text-gray-600">${escapeHtml(checkIn)}</span>
      </td>
      <td class="px-6 py-4">
        <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-sm">${escapeHtml(paymentMethod)}</span>
      </td>
      <td class="px-6 py-4">
        <span class="font-semibold text-indigo-600">${depositAmount}</span>
      </td>
      <td class="px-6 py-4">
        <span class="px-3 py-1 rounded-full text-xs font-semibold ${
          status.cls
        }">${status.label}</span>
      </td>
    </tr>
  `;
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
