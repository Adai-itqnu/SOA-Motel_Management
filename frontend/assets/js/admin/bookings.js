/**
 * Admin Bookings History
 * - List all bookings with filtering
 * - Approve / Reject / View details
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
    case "pending":
      return { label: "Chờ duyệt", cls: "bg-amber-100 text-amber-700" };
    case "deposit_pending":
      return { label: "Chờ đặt cọc", cls: "bg-orange-100 text-orange-700" };
    case "deposit_paid":
      return { label: "Đã đặt cọc", cls: "bg-indigo-100 text-indigo-700" };
    case "approved":
    case "confirmed":
      return { label: "Đã xác nhận", cls: "bg-green-100 text-green-700" };
    case "rejected":
      return { label: "Bị từ chối", cls: "bg-red-100 text-red-700" };
    case "cancelled":
      return { label: "Đã hủy", cls: "bg-gray-100 text-gray-600" };
    case "expired":
      return { label: "Hết hạn", cls: "bg-gray-100 text-gray-500" };
    default:
      return { label: status || "--", cls: "bg-gray-100 text-gray-700" };
  }
}

function depositBadge(status) {
  switch (status) {
    case "paid":
      return { label: "Đã thanh toán", cls: "bg-green-100 text-green-700" };
    case "pending":
      return { label: "Chưa thanh toán", cls: "bg-amber-100 text-amber-700" };
    case "refunded":
      return { label: "Đã hoàn cọc", cls: "bg-gray-100 text-gray-700" };
    default:
      return { label: status || "--", cls: "bg-gray-100 text-gray-700" };
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

  allBookings = res.data?.bookings || [];
  updateStats();
  renderBookings();
}

function updateStats() {
  const total = allBookings.length;
  const pending = allBookings.filter(
    (b) => b.status === "pending" || b.status === "deposit_pending"
  ).length;
  const confirmed = allBookings.filter(
    (b) =>
      b.status === "confirmed" ||
      b.status === "approved" ||
      b.status === "deposit_paid"
  ).length;
  const cancelled = allBookings.filter(
    (b) =>
      b.status === "cancelled" ||
      b.status === "rejected" ||
      b.status === "expired"
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

function canApprove(b) {
  return b.status === "deposit_paid" && b.deposit_status === "paid";
}

function canReject(b) {
  return (
    b.status !== "approved" &&
    b.status !== "confirmed" &&
    b.status !== "cancelled" &&
    b.status !== "rejected" &&
    b.status !== "expired"
  );
}

function renderBookingRow(b) {
  const status = statusBadge(b.status);
  const createdAt = (b.created_at || "").split("T")[0] || "--";
  const userName = b.user_name || b.user_fullname || b.user_id || "--";
  const roomCode = b.room_code || b.room_name || b.room_id || "--";

  const approveBtn = canApprove(b)
    ? `<button onclick="approveBooking('${escapeHtml(
        b._id
      )}')" class="text-green-600 hover:text-green-800 font-medium text-sm">Duyệt</button>`
    : "";
  const rejectBtn = canReject(b)
    ? `<button onclick="rejectBooking('${escapeHtml(
        b._id
      )}')" class="text-red-600 hover:text-red-800 font-medium text-sm">Từ chối</button>`
    : "";

  return `
    <tr class="hover:bg-gray-50 transition-colors">
      <td class="px-6 py-4">
        <span class="font-mono text-sm font-semibold text-indigo-600">${escapeHtml(
          b._id || ""
        )}</span>
      </td>
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
        <span class="text-gray-600">${escapeHtml(createdAt)}</span>
      </td>
      <td class="px-6 py-4">
        <span class="px-3 py-1 rounded-full text-xs font-semibold ${
          status.cls
        }">${status.label}</span>
      </td>
      <td class="px-6 py-4 text-center">
        <div class="flex items-center justify-center gap-3">
          ${approveBtn}
          ${rejectBtn}
          <button onclick="viewBookingDetail('${escapeHtml(
            b._id
          )}')" class="text-indigo-600 hover:text-indigo-800 font-medium text-sm">Chi tiết</button>
        </div>
      </td>
    </tr>
  `;
}

function viewBookingDetail(bookingId) {
  const b = allBookings.find((x) => x._id === bookingId);
  if (!b) return;

  const status = statusBadge(b.status);
  const dep = depositBadge(b.deposit_status);
  const depositAmount = UI.formatCurrency(b.deposit_amount || 0);
  const checkIn = (b.check_in_date || "").split("T")[0] || "--";
  const createdAt = (b.created_at || "").split("T")[0] || "--";

  alert(
    `Chi tiết đặt phòng ${b._id}:\n\n` +
      `Khách hàng: ${b.user_name || b.user_id}\n` +
      `Phòng: ${b.room_code || b.room_id}\n` +
      `Trạng thái: ${status.label}\n` +
      `Tiền cọc: ${depositAmount} (${dep.label})\n` +
      `Ngày nhận phòng: ${checkIn}\n` +
      `Ngày tạo: ${createdAt}\n` +
      (b.message ? `Ghi chú: ${b.message}\n` : "") +
      (b.admin_note ? `Ghi chú admin: ${b.admin_note}` : "")
  );
}

async function approveBooking(bookingId) {
  UI.hide("adminBookingsError");
  UI.hide("adminBookingsSuccess");

  const adminNote = window.prompt("Ghi chú admin (tuỳ chọn):", "") || "";
  const res = await API.put(`/bookings/${bookingId}/approve`, {
    admin_note: adminNote,
  });

  if (!res.ok) {
    UI.showError(
      "adminBookingsError",
      res.data?.message || "Không thể duyệt booking"
    );
    return;
  }

  const successEl = document.getElementById("adminBookingsSuccess");
  successEl.textContent = res.data?.message || "Duyệt đặt phòng thành công!";
  successEl.classList.remove("hidden");

  loadBookings();
}

async function rejectBooking(bookingId) {
  UI.hide("adminBookingsError");
  UI.hide("adminBookingsSuccess");

  const reason = window.prompt("Lý do từ chối:", "") || "";
  const res = await API.put(`/bookings/${bookingId}/reject`, { reason });

  if (!res.ok) {
    UI.showError(
      "adminBookingsError",
      res.data?.message || "Không thể từ chối booking"
    );
    return;
  }

  const successEl = document.getElementById("adminBookingsSuccess");
  successEl.textContent = res.data?.message || "Từ chối đặt phòng thành công!";
  successEl.classList.remove("hidden");

  loadBookings();
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
