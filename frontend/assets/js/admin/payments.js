/**
 * Admin Payments (Invoices)
 * - List all payments (deposit + monthly bill)
 */

document.addEventListener("DOMContentLoaded", () => {
  if (typeof AdminLayout !== "undefined") {
    AdminLayout.init();
  } else {
    if (!Auth.checkAuth("admin")) return;
  }

  loadPayments();
});

function logout() {
  Auth.logout();
}

function refreshPayments() {
  loadPayments();
}

function paymentTypeLabel(t) {
  switch (t) {
    case "room_reservation_deposit":
      return { label: "Cọc giữ phòng", cls: "bg-indigo-100 text-indigo-700" };
    case "booking_deposit":
      return {
        label: "Cọc booking (legacy)",
        cls: "bg-gray-100 text-gray-700",
      };
    case "bill_payment":
      return { label: "Thanh toán hóa đơn", cls: "bg-blue-100 text-blue-700" };
    case "booking":
      return { label: "Cọc (legacy)", cls: "bg-indigo-100 text-indigo-700" };
    case "contract":
      return { label: "Cọc hợp đồng", cls: "bg-purple-100 text-purple-700" };
    default:
      return { label: t || "--", cls: "bg-gray-100 text-gray-700" };
  }
}

function statusBadge(status) {
  switch (status) {
    case "completed":
      return { label: "Đã thanh toán", cls: "bg-green-100 text-green-700" };
    case "pending":
      return { label: "Đang chờ", cls: "bg-amber-100 text-amber-700" };
    case "failed":
      return { label: "Thất bại", cls: "bg-red-100 text-red-700" };
    default:
      return { label: status || "--", cls: "bg-gray-100 text-gray-700" };
  }
}

async function loadPayments() {
  UI.hide("adminPaymentsError");
  UI.hide("adminPaymentsSuccess");
  UI.show("adminPaymentsLoading");
  UI.hide("adminPaymentsEmpty");
  UI.hide("adminPaymentsList");

  const res = await API.get("/payments");
  UI.hide("adminPaymentsLoading");

  if (!res.ok) {
    UI.showError(
      "adminPaymentsError",
      res.data?.message || "Không thể tải danh sách thanh toán"
    );
    return;
  }

  const payments = res.data?.payments || [];
  if (payments.length === 0) {
    UI.show("adminPaymentsEmpty");
    return;
  }

  const list = document.getElementById("adminPaymentsList");
  list.innerHTML = payments.map(renderPaymentItem).join("");
  UI.show("adminPaymentsList");
}

function renderPaymentItem(p) {
  const type = paymentTypeLabel(p.payment_type);
  const st = statusBadge(p.status);
  const amount = UI.formatCurrency(p.amount || p.amount_vnd || 0);

  const createdAt = (p.created_at || "").split("T")[0] || "--";
  const updatedAt = (p.updated_at || "").split("T")[0] || "--";

  const bookingId = p.booking_id || "";
  const roomId = p.room_id || "";
  const billId = p.bill_id || "";
  const tenantId = p.tenant_id || "";

  const txnId = p.transaction_id || p.provider_txn_id || "";
  const respCode = p.provider_response_code || "";

  return `
    <div class="bg-white rounded-2xl shadow-lg p-6">
      <div class="flex items-start justify-between gap-3 flex-col sm:flex-row">
        <div>
          <h3 class="text-lg font-bold text-gray-800">Payment ${escapeHtml(
            p._id || p.id || ""
          )}</h3>
          <p class="text-sm text-gray-500">Phương thức: <span class="font-semibold text-gray-800">${escapeHtml(
            p.method || "--"
          )}</span></p>
        </div>
        <div class="flex items-center gap-2">
          <span class="px-3 py-1 rounded-full text-xs font-semibold ${
            type.cls
          }">${type.label}</span>
          <span class="px-3 py-1 rounded-full text-xs font-semibold ${
            st.cls
          }">${st.label}</span>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Số tiền</p>
          <p class="font-semibold text-gray-800">${amount}</p>
        </div>
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Room / Booking</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            roomId || "--"
          )} / ${escapeHtml(bookingId || "--")}</p>
        </div>
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Bill ID</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            billId || "--"
          )}</p>
        </div>
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Tenant/User ID</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            tenantId || "--"
          )}</p>
        </div>
      </div>

      <div class="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Transaction ID</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            txnId || "--"
          )}</p>
        </div>
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">VNPay Code</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            respCode || "--"
          )}</p>
        </div>
        <div class="bg-gray-50 rounded-xl p-3">
          <p class="text-gray-500">Ngày tạo / cập nhật</p>
          <p class="font-semibold text-gray-800">${escapeHtml(
            createdAt
          )} / ${escapeHtml(updatedAt)}</p>
        </div>
      </div>
    </div>
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
