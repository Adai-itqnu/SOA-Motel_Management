(function () {
let allPayments = [];
let allBills = [];
let allTenants = [];

// Format price
function formatPrice(price) {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
  }).format(price);
}

// Format date
function formatDate(dateString) {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleDateString("vi-VN");
}

// Load payments data
window.loadPaymentsData = async function loadPaymentsData() {
  try {
    const headers = getAuthHeader();
    const response = await fetch(buildApiUrl("/api/payments"), {
      headers,
    });
    if (response.status === 401) {
      console.error("Unauthorized - redirecting to login");
      window.location.href = "/login";
      return;
    }
    if (!response.ok) throw new Error("Không thể tải danh sách thanh toán");
    const data = await response.json();
    allPayments = data.payments || [];
    filterPayments();
    await loadBillsAndTenants();
  } catch (error) {
    console.error("Error loading payments:", error);
  }
};

// Load bills and tenants for display
async function loadBillsAndTenants() {
  try {
    const headers = getAuthHeader();
    
    // Load bills
    const billsResponse = await fetch(buildApiUrl("/api/bills"), { headers });
    if (billsResponse.ok) {
      const billsData = await billsResponse.json();
      allBills = billsData.bills || [];
    }
    
    // Load tenants
    const tenantsResponse = await fetch(buildApiUrl("/api/tenants"), { headers });
    if (tenantsResponse.ok) {
      const tenantsData = await tenantsResponse.json();
      allTenants = tenantsData.tenants || [];
    }
  } catch (error) {
    console.error("Error loading bills/tenants:", error);
  }
}

// Filter payments
function filterPayments() {
  const searchInput = document.getElementById("paymentSearchInput");
  const statusFilter = document.getElementById("paymentStatusFilter");
  const methodFilter = document.getElementById("paymentMethodFilter");

  if (!searchInput || !statusFilter) return;

  const searchText = searchInput.value.toLowerCase();
  const statusFilterValue = statusFilter.value;
  const methodFilterValue = methodFilter ? methodFilter.value : "";

  let filtered = allPayments.filter((payment) => {
    const matchSearch = 
      (payment._id || payment.id || "").toLowerCase().includes(searchText) ||
      (payment.bill_id || "").toLowerCase().includes(searchText) ||
      (payment.tenant_id || "").toLowerCase().includes(searchText);
    const matchStatus = !statusFilterValue || payment.status === statusFilterValue;
    const matchMethod = !methodFilterValue || payment.method === methodFilterValue;
    return matchSearch && matchStatus && matchMethod;
  });

  renderPayments(filtered);
}

// Render payments
function renderPayments(payments) {
  const tbody = document.getElementById("paymentsTableBody");
  if (!tbody) return;

  if (payments.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" style="text-align: center;">Không tìm thấy thanh toán nào</td></tr>';
    return;
  }

  tbody.innerHTML = payments
    .map((payment) => {
      const statusClass = {
        pending: "status-pending",
        completed: "status-completed",
        failed: "status-failed",
      }[payment.status] || "";
      
      const statusText = {
        pending: "Đang chờ",
        completed: "Hoàn thành",
        failed: "Thất bại",
      }[payment.status] || payment.status;
      
      const methodText = {
        cash: "Tiền mặt",
        bank_transfer: "Chuyển khoản",
        vnpay: "VNpay",
        momo: "MoMo",
      }[payment.method] || payment.method;
      
      const paymentId = payment._id || payment.id;
      
      // Get bill info
      const bill = allBills.find(b => (b._id || b.id) === payment.bill_id);
      const billDisplay = bill ? (bill._id || bill.id) : (payment.bill_id || "N/A");
      
      // Get tenant name
      const tenant = allTenants.find(t => (t._id || t.id) === payment.tenant_id);
      const tenantName = tenant ? tenant.name : payment.tenant_id;
      
      return `
        <tr>
            <td><strong>${paymentId}</strong></td>
            <td>${billDisplay}</td>
            <td>${tenantName}</td>
            <td>${formatPrice(payment.amount || 0)}</td>
            <td>${methodText}</td>
            <td>${formatDate(payment.payment_date)}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>
                <button class="btn-small btn-primary" onclick="viewPaymentDetail('${paymentId}')">Chi tiết</button>
            </td>
        </tr>
    `;
    })
    .join("");
}

// View payment detail
window.viewPaymentDetail = async function viewPaymentDetail(paymentId) {
  try {
    const headers = getAuthHeader();
    const response = await fetch(buildApiUrl(`/api/payments/${paymentId}`), {
      headers,
    });
    
    if (!response.ok) throw new Error("Không thể tải thông tin thanh toán");
    const data = await response.json();
    const payment = data.payment || data;
    
    // Show payment details in alert or modal
    const details = `
Mã thanh toán: ${payment._id || payment.id}
Hóa đơn: ${payment.bill_id || "N/A"}
Người thuê: ${payment.tenant_id || "N/A"}
Số tiền: ${formatPrice(payment.amount || 0)}
Phương thức: ${payment.method || "N/A"}
Ngày thanh toán: ${formatDate(payment.payment_date)}
Trạng thái: ${payment.status || "N/A"}
${payment.transaction_id ? `Transaction ID: ${payment.transaction_id}` : ""}
    `;
    
    alert(details);
  } catch (error) {
    console.error("Error loading payment:", error);
    alert("Không thể tải thông tin thanh toán");
  }
};

// Event listeners
document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("paymentSearchInput");
  const statusFilter = document.getElementById("paymentStatusFilter");
  const methodFilter = document.getElementById("paymentMethodFilter");
  
  if (searchInput) {
    searchInput.addEventListener("input", filterPayments);
  }
  if (statusFilter) {
    statusFilter.addEventListener("change", filterPayments);
  }
  if (methodFilter) {
    methodFilter.addEventListener("change", filterPayments);
  }
});

// Mark script as loaded
window.scriptsLoaded = window.scriptsLoaded || {};
window.scriptsLoaded.payments = true;
})();

