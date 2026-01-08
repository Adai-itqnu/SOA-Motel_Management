/**
 * User Bills page logic
 * Uses Layout module for header/footer/navigation
 */
let bills = [];
let currentFilter = "all";
let selectedBillId = null;

// Entry
document.addEventListener("DOMContentLoaded", () => {
  // Initialize layout first
  if (typeof Layout !== "undefined") {
    Layout.init("bills");
    Layout.setPageTitle("Hóa đơn");
  } else if (typeof Auth !== "undefined" && !Auth.isLoggedIn()) {
    window.location.href = "/auth/login.html";
    return;
  }

  wireTabs();
  wireListActions();
  wireModal();
  loadBills();
  checkVNPayResult();
});

function checkVNPayResult() {
  const params = new URLSearchParams(window.location.search);
  const vnpayStatus = params.get("vnpay");
  if (!vnpayStatus) return;

  const billId = params.get("bill_id");

  // Clean URL
  window.history.replaceState({}, "", "/user/bills.html");

  let cfg = { 
    title: "Thanh toán", 
    msg: "", 
    bgClass: "bg-green-500",
    icon: "check_circle"
  };

  if (vnpayStatus === "success") {
    cfg = {
      title: "Thanh toán hóa đơn thành công!",
      msg: billId ? `Hóa đơn ${billId} đã được thanh toán.` : "Giao dịch đã được xác nhận.",
      bgClass: "bg-green-500",
      icon: "check_circle"
    };
  } else if (vnpayStatus === "cancel") {
    cfg = {
      title: "Thanh toán bị hủy",
      msg: "Bạn đã hủy giao dịch thanh toán hóa đơn.",
      bgClass: "bg-amber-500",
      icon: "warning"
    };
  } else if (vnpayStatus === "pending") {
    cfg = {
      title: "Đang xử lý",
      msg: "Giao dịch thanh toán hóa đơn đang chờ xác nhận...",
      bgClass: "bg-blue-500",
      icon: "pending"
    };
  } else {
    cfg = {
      title: "Thanh toán thất bại",
      msg: "Có lỗi xảy ra trong quá trình thanh toán hóa đơn.",
      bgClass: "bg-red-500",
      icon: "error"
    };
  }

  // Create and show toast notification
  const toast = document.createElement("div");
  toast.className = "fixed top-20 left-1/2 -translate-x-1/2 z-50 max-w-2xl w-full px-4";
  toast.style.transition = "transform 0.4s ease-out, opacity 0.4s ease-out";
  toast.style.transform = "translateY(-100%)";
  toast.style.opacity = "0";
  
  toast.innerHTML = `
    <div class="flex items-center justify-center gap-3 ${cfg.bgClass} text-white px-6 py-3 rounded-xl shadow-lg">
      <span class="material-symbols-outlined text-xl">${cfg.icon}</span>
      <span class="font-medium">${cfg.title}</span>
      <span class="text-white/90">${cfg.msg}</span>
      <button onclick="this.closest('div').parentElement.remove();" class="ml-4 hover:bg-white/20 rounded-full p-1 transition-colors">
        <span class="material-symbols-outlined text-lg">close</span>
      </button>
    </div>
  `;
  document.body.appendChild(toast);
  
  // Slide down animation
  setTimeout(() => {
    toast.style.transform = "translateY(0)";
    toast.style.opacity = "1";
  }, 100);

  // Auto hide after 8 seconds
  setTimeout(() => {
    toast.style.transform = "translateY(-100%)";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 8000);
}

function wireTabs() {
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.getAttribute("data-filter");
      if (!filter) return;
      currentFilter = filter;
      highlightActiveTab(filter);
      renderList();
    });
  });
}

function highlightActiveTab(filter) {
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    const isActive = btn.getAttribute("data-filter") === filter;
    const labelSpan = btn.querySelector("span:first-child");
    const countSpan = btn.querySelector("span:last-child");

    if (isActive) {
      btn.className =
        "group flex items-center gap-2 border-b-[3px] border-primary pb-3 px-1";
      if (labelSpan) {
        labelSpan.classList.add("text-primary", "font-bold");
        labelSpan.classList.remove("text-gray-500");
      }
      if (countSpan) {
        countSpan.classList.add("bg-primary/10", "text-primary");
        countSpan.classList.remove("bg-gray-100", "text-gray-500");
      }
    } else {
      btn.className =
        "group flex items-center gap-2 border-b-[3px] border-transparent hover:border-gray-200 pb-3 px-1 transition-colors";
      if (labelSpan) {
        labelSpan.classList.remove("text-primary", "font-bold");
        labelSpan.classList.add("text-gray-500");
      }
      if (countSpan) {
        countSpan.classList.remove("bg-primary/10", "text-primary");
        countSpan.classList.add("bg-gray-100", "text-gray-500");
      }
    }
  });
}

function wireListActions() {
  const list = document.getElementById("billList");
  if (!list) return;

  list.addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;
    const id = target.getAttribute("data-id");
    if (!id) return;
    if (target.dataset.action === "detail") {
      openBillModal(id, false);
    }
    if (target.dataset.action === "pay") {
      openBillModal(id, true);
    }
  });
}

function wireModal() {
  const modal = document.getElementById("billModal");
  if (!modal) return;

  const closeButtons = modal.querySelectorAll("[data-close]");
  closeButtons.forEach((btn) =>
    btn.addEventListener("click", () => modal.classList.add("hidden"))
  );

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
    }
  });

  // ESC key to close
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      modal.classList.add("hidden");
    }
  });
}

async function loadBills() {
  showLoading();
  try {
    const res = await API.get("/bills");
    if (!res.ok) {
      showError(res.data?.message || "Không thể tải hóa đơn");
      return;
    }
    // Support both { bills: [...] } and direct array response
    const data = res.data;
    if (Array.isArray(data)) {
      bills = data;
    } else if (data && Array.isArray(data.bills)) {
      bills = data.bills;
    } else {
      bills = [];
    }

    renderStats();
    renderList();
  } catch (error) {
    console.error("Load bills error:", error);
    showError("Lỗi kết nối server");
  }
}

function showLoading() {
  const loading = document.getElementById("loadingState");
  const error = document.getElementById("errorState");
  const empty = document.getElementById("emptyState");
  const list = document.getElementById("billList");

  if (loading) loading.classList.remove("hidden");
  if (error) error.classList.add("hidden");
  if (empty) empty.classList.add("hidden");
  if (list) list.classList.add("hidden");
}

function showError(message) {
  const loading = document.getElementById("loadingState");
  const error = document.getElementById("errorState");
  const empty = document.getElementById("emptyState");
  const list = document.getElementById("billList");

  if (loading) loading.classList.add("hidden");
  if (empty) empty.classList.add("hidden");
  if (list) list.classList.add("hidden");

  if (error) {
    error.classList.remove("hidden");
    const msgEl = error.querySelector("span");
    if (msgEl) msgEl.textContent = message || "Đã có lỗi xảy ra";
  }
}

function renderStats() {
  // Normalize status for comparison
  const isPending = (b) => {
    const s = (b.status || "").toLowerCase();
    return s === "pending" || s === "unpaid" || s === "overdue";
  };
  const isPaid = (b) => (b.status || "").toLowerCase() === "paid";

  const pendingBills = bills.filter(isPending);
  const paidBills = bills.filter(isPaid);

  // API returns 'total' field
  const totalUnpaid = pendingBills.reduce(
    (sum, b) => sum + (b.total || b.total_amount || b.totalAmount || 0),
    0
  );
  const totalPaid = paidBills.reduce(
    (sum, b) => sum + (b.total || b.total_amount || b.totalAmount || 0),
    0
  );

  // Update stat cards
  const statPending = document.getElementById("statPendingCount");
  const statUnpaid = document.getElementById("statUnpaidTotal");
  const statPaid = document.getElementById("statPaidTotal");

  if (statPending) statPending.textContent = pendingBills.length;
  if (statUnpaid) statUnpaid.textContent = formatCurrency(totalUnpaid);
  if (statPaid) statPaid.textContent = formatCurrency(totalPaid);

  // Update tab counts
  const tabAll = document.getElementById("tabAllCount");
  const tabPending = document.getElementById("tabPendingCount");
  const tabPaid = document.getElementById("tabPaidCount");

  if (tabAll) tabAll.textContent = bills.length;
  if (tabPending) tabPending.textContent = pendingBills.length;
  if (tabPaid) tabPaid.textContent = paidBills.length;
}

function renderList() {
  const listEl = document.getElementById("billList");
  const loading = document.getElementById("loadingState");
  const empty = document.getElementById("emptyState");

  if (loading) loading.classList.add("hidden");

  if (!listEl) return;

  const filtered = filterBills();

  if (filtered.length === 0) {
    if (empty) empty.classList.remove("hidden");
    listEl.classList.add("hidden");
    return;
  }

  if (empty) empty.classList.add("hidden");
  listEl.classList.remove("hidden");
  listEl.innerHTML = filtered.map(renderBillCard).join("");
}

function filterBills() {
  const isPending = (b) => {
    const s = (b.status || "").toLowerCase();
    return s === "pending" || s === "unpaid" || s === "overdue";
  };
  const isPaid = (b) => (b.status || "").toLowerCase() === "paid";

  if (currentFilter === "pending") {
    return bills.filter(isPending);
  }
  if (currentFilter === "paid") {
    return bills.filter(isPaid);
  }
  return bills;
}

function renderBillCard(bill) {
  const status = getStatusInfo(bill.status);
  const due = getDueDate(bill);
  const paidDate =
    bill.paid_at || bill.paidAt || bill.paid_date || bill.paidDate;
  // Parse month format: "MM/YYYY" or separate month/year fields
  let month = "--",
    year = "--";
  if (bill.month && bill.month.includes("/")) {
    [month, year] = bill.month.split("/");
  } else {
    month = bill.month || bill.billing_month || "--";
    year = bill.year || bill.billing_year || "--";
  }
  const roomRent =
    bill.room_fee || bill.room_rent || bill.roomRent || bill.rent || 0;
  const electricityCost =
    bill.electric_fee ||
    bill.electricity_cost ||
    bill.electricityCost ||
    bill.electric ||
    0;
  const waterCost =
    bill.water_fee || bill.water_cost || bill.waterCost || bill.water || 0;
  const totalAmount = bill.total || bill.total_amount || bill.totalAmount || 0;

  return `
    <div class="group relative flex flex-col md:flex-row items-start md:items-center justify-between gap-4 md:gap-6 rounded-xl bg-white p-5 border border-gray-100 shadow-sm hover:shadow-lg hover:border-primary/20 transition-all">
      <div class="flex items-center gap-4 min-w-[180px]">
        <div class="flex h-12 w-12 items-center justify-center rounded-xl ${
          status.iconBg
        } transition-colors">
          <span class="material-symbols-outlined text-[24px]">calendar_month</span>
        </div>
        <div class="flex flex-col">
          <p class="text-gray-900 text-lg font-bold">Tháng ${month}/${year}</p>
          <p class="text-sm ${
            status.isOverdue ? "text-red-500 font-medium" : "text-gray-500"
          }">
            ${
              paidDate
                ? `Thanh toán: ${formatDate(paidDate)}`
                : due
                ? `${status.isOverdue ? "Quá hạn" : "Hạn"}: ${formatDate(due)}`
                : ""
            }
          </p>
        </div>
      </div>
      <div class="flex flex-1 flex-col gap-2">
        <div class="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600">
          <span class="flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px] text-gray-400">home</span>
            Phòng: <strong class="text-gray-900 ml-1">${formatCurrency(
              roomRent
            )}</strong>
          </span>
          <span class="flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px] text-yellow-500">bolt</span>
            Điện: <strong class="text-gray-900 ml-1">${formatCurrency(
              electricityCost
            )}</strong>
          </span>
          <span class="flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px] text-blue-500">water_drop</span>
            Nước: <strong class="text-gray-900 ml-1">${formatCurrency(
              waterCost
            )}</strong>
          </span>
        </div>
        <div class="flex items-center gap-2 mt-1">
          <span class="text-sm font-medium text-gray-500">Tổng cộng:</span>
          <span class="text-xl font-bold ${
            status.isPaid ? "text-gray-900" : "text-primary"
          }">${formatCurrency(totalAmount)}</span>
        </div>
      </div>
      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full md:w-auto mt-2 md:mt-0">
        <span class="inline-flex items-center gap-1.5 rounded-full ${
          status.chipBg
        } px-3 py-1 text-xs font-bold ${status.chipText} border ${
    status.chipBorder
  }">
          <span class="size-1.5 rounded-full ${status.chipDot}"></span>
          ${status.label}
        </span>
        <div class="flex gap-2 w-full sm:w-auto">
          <button data-action="detail" data-id="${
            bill._id || bill.id
          }" class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-white text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors">
            Chi tiết
          </button>
          ${
            status.isPaid
              ? ""
              : `
            <button data-action="pay" data-id="${
              bill._id || bill.id
            }" class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-bold hover:bg-primary-hover shadow-md shadow-primary/20 transition-all">
              <span class="material-symbols-outlined text-[18px]">credit_card</span>
              Thanh toán
            </button>
          `
          }
        </div>
      </div>
    </div>
  `;
}

function openBillModal(id, fromPay) {
  const modal = document.getElementById("billModal");
  const body = document.getElementById("modalBody");
  const payBtn = document.getElementById("modalPayBtn");
  if (!modal || !body) return;

  const bill = bills.find((b) => (b._id || b.id) === id);
  if (!bill) return;
  selectedBillId = id;

  const status = getStatusInfo(bill.status);
  const due = getDueDate(bill);
  const paidDate =
    bill.paid_at || bill.paidAt || bill.paid_date || bill.paidDate;
  const billCode = getBillCode(bill);
  // Parse month format: "MM/YYYY" or separate month/year fields
  let month = "--",
    year = "--";
  if (bill.month && bill.month.includes("/")) {
    [month, year] = bill.month.split("/");
  } else {
    month = bill.month || bill.billing_month || "--";
    year = bill.year || bill.billing_year || "--";
  }
  const totalAmount = bill.total || bill.total_amount || bill.totalAmount || 0;

  body.innerHTML = `
    <div class="mb-6 flex items-center justify-between ${status.bannerClass}">
      <div class="flex items-center gap-2 ${status.bannerTextClass}">
        <span class="material-symbols-outlined">${status.bannerIcon}</span>
        <span class="text-sm font-medium">${status.bannerMessage}</span>
      </div>
      ${
        due || paidDate
          ? `
        <span class="text-xs font-bold bg-white ${
          status.badgeClass
        } px-2 py-1 rounded">
          ${status.isPaid ? "Ngày TT" : "Hạn"}: ${
              paidDate ? formatDate(paidDate) : formatDate(due)
            }
        </span>
      `
          : ""
      }
    </div>
    <div class="overflow-hidden rounded-lg border border-gray-200 mb-6">
      <table class="w-full text-sm text-left">
        <thead class="bg-gray-50 text-gray-700 font-semibold border-b border-gray-200">
          <tr>
            <th class="px-4 py-3">Dịch vụ</th>
            <th class="px-4 py-3 text-right">Chỉ số</th>
            <th class="px-4 py-3 text-right">Đơn giá</th>
            <th class="px-4 py-3 text-right">Thành tiền</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          ${renderRow(
            "Tiền phòng",
            "-",
            "-",
            bill.room_fee || bill.room_rent || bill.roomRent || bill.rent
          )}
          ${renderElectricRow(bill)}
          ${renderWaterRow(bill)}
          ${renderOtherFeeRow(bill)}
          <tr class="bg-primary/5">
            <td class="px-4 py-3 font-bold text-primary" colspan="3">Tổng cộng</td>
            <td class="px-4 py-3 text-right font-bold text-primary text-base">${formatCurrency(
              totalAmount
            )}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="text-xs text-gray-500 italic">* Vui lòng thanh toán trước ngày ${
      due ? formatDate(due) : "hạn được ghi trên hóa đơn"
    } để tránh phí phạt.</div>
  `;

  const titleEl = document.getElementById("modalBillTitle");
  const codeEl = document.getElementById("modalBillCode");
  if (titleEl) titleEl.textContent = `Chi tiết Hóa đơn tháng ${month}/${year}`;
  if (codeEl) codeEl.textContent = billCode ? `Mã hóa đơn: ${billCode}` : "";

  if (payBtn) {
    if (status.isPaid) {
      payBtn.classList.add("hidden");
    } else {
      payBtn.classList.remove("hidden");
      payBtn.onclick = () => startPayment(bill);
    }
  }

  modal.classList.remove("hidden");

  if (fromPay && payBtn && !status.isPaid) {
    payBtn.focus();
  }
}

function renderRow(title, meterText, priceText, amount) {
  return `
    <tr>
      <td class="px-4 py-3 font-medium">${title}</td>
      <td class="px-4 py-3 text-right text-gray-500">${meterText || "-"}</td>
      <td class="px-4 py-3 text-right text-gray-500">${priceText || "-"}</td>
      <td class="px-4 py-3 text-right font-medium">${formatCurrency(
        amount
      )}</td>
    </tr>
  `;
}

function renderElectricRow(bill) {
  // API returns: electric_old, electric_new, electric_fee
  // Use ?? (nullish coalescing) to handle 0 values correctly
  const newMeter =
    bill.electric_new ?? bill.electricity_new ?? bill.electricityNew ?? null;
  const oldMeter =
    bill.electric_old ?? bill.electricity_old ?? bill.electricityOld ?? null;
  const price =
    bill.electric_price ||
    bill.electricity_price ||
    bill.electricityPrice ||
    3500;
  const cost =
    bill.electric_fee ||
    bill.electricity_cost ||
    bill.electricityCost ||
    bill.electric ||
    0;

  let meterBlock = "-";
  if (newMeter != null && oldMeter != null) {
    const diff = newMeter - oldMeter;
    meterBlock = `<div class="flex flex-col items-end text-xs"><span>Mới: ${newMeter}</span><span>Cũ: ${oldMeter}</span><span class="text-gray-900 font-medium">SD: ${diff} kWh</span></div>`;
  }

  const priceText = price ? `${formatCurrency(price)}/kWh` : "-";
  return renderRow("Điện", meterBlock, priceText, cost);
}

function renderWaterRow(bill) {
  // API returns: water_old, water_new, water_fee
  // Use ?? (nullish coalescing) to handle 0 values correctly
  const newMeter = bill.water_new ?? bill.waterNew ?? null;
  const oldMeter = bill.water_old ?? bill.waterOld ?? null;
  const price = bill.water_price || bill.waterPrice || 15000;
  const cost =
    bill.water_fee || bill.water_cost || bill.waterCost || bill.water || 0;

  let meterBlock = "-";
  if (newMeter != null && oldMeter != null) {
    const diff = newMeter - oldMeter;
    meterBlock = `<div class="flex flex-col items-end text-xs"><span>Mới: ${newMeter}</span><span>Cũ: ${oldMeter}</span><span class="text-gray-900 font-medium">SD: ${diff} m³</span></div>`;
  }

  const priceText = price ? `${formatCurrency(price)}/m³` : "-";
  return renderRow("Nước", meterBlock, priceText, cost);
}

function renderOtherFeeRow(bill) {
  // API returns: other_fee
  const amount =
    bill.other_fee || bill.other_fees || bill.otherFees || bill.other_cost || 0;
  if (!amount) return "";
  return renderRow("Phí khác", "-", "-", amount);
}

async function startPayment(bill) {
  if (!bill) return;

  // If bill has payment URL, use it
  if (bill.payment_url || bill.paymentUrl) {
    window.open(bill.payment_url || bill.paymentUrl, "_blank");
    return;
  }

  // Try to create payment via API
  try {
    const billId = bill._id || bill.id;
    const res = await API.post("/vnpay/bill", {
      bill_id: billId,
    });

    if (res.ok && res.data?.payment_url) {
      window.location.href = res.data.payment_url;
      return;
    }

    alert(
      "Chức năng thanh toán online đang được phát triển. Vui lòng liên hệ chủ trọ để thanh toán."
    );
  } catch (error) {
    console.error("Payment error:", error);
    alert("Không thể khởi tạo thanh toán. Vui lòng thử lại sau.");
  }
}

function getStatusInfo(status) {
  const normalized = (status || "").toLowerCase();

  if (normalized === "paid") {
    return {
      label: "Đã thanh toán",
      isPaid: true,
      isOverdue: false,
      chipBg: "bg-green-50",
      chipText: "text-green-700",
      chipBorder: "border-green-200",
      chipDot: "bg-green-500",
      iconBg: "bg-green-50 text-green-600",
      bannerClass: "bg-green-50 p-3 rounded-lg border border-green-200",
      bannerTextClass: "text-green-800",
      badgeClass: "text-green-700 border border-green-200",
      bannerIcon: "task_alt",
      bannerMessage: "Hóa đơn đã được thanh toán",
    };
  }

  if (normalized === "overdue") {
    return {
      label: "Quá hạn",
      isPaid: false,
      isOverdue: true,
      chipBg: "bg-red-50",
      chipText: "text-red-700",
      chipBorder: "border-red-200",
      chipDot: "bg-red-500",
      iconBg: "bg-red-50 text-red-600",
      bannerClass: "bg-red-50 p-3 rounded-lg border border-red-200",
      bannerTextClass: "text-red-800",
      badgeClass: "text-red-700 border border-red-200",
      bannerIcon: "warning",
      bannerMessage: "Hóa đơn đã quá hạn thanh toán",
    };
  }

  // pending, unpaid, or any other status
  return {
    label: "Chờ thanh toán",
    isPaid: false,
    isOverdue: false,
    chipBg: "bg-amber-50",
    chipText: "text-amber-700",
    chipBorder: "border-amber-200",
    chipDot: "bg-amber-500",
    iconBg: "bg-amber-50 text-amber-600",
    bannerClass: "bg-amber-50 p-3 rounded-lg border border-amber-200",
    bannerTextClass: "text-amber-800",
    badgeClass: "text-amber-700 border border-amber-200",
    bannerIcon: "schedule",
    bannerMessage: "Hóa đơn đang chờ thanh toán",
  };
}

function getDueDate(bill) {
  return (
    bill.due_date ||
    bill.dueDate ||
    bill.due_at ||
    bill.dueAt ||
    bill.due ||
    null
  );
}

function getBillCode(bill) {
  return (
    bill.code ||
    bill.bill_code ||
    bill.billCode ||
    bill.invoice_code ||
    bill.invoiceCode ||
    ""
  );
}

function formatCurrency(amount) {
  return new Intl.NumberFormat("vi-VN").format(amount || 0) + "đ";
}

function formatDate(dateStr) {
  if (!dateStr) return "--";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;
  return date.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
