(function () {
const API_GATEWAY = window.API_GATEWAY || "";

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

/**
 * Create a deposit payment record and redirect user to VNPay.
 * Reused by booking flow and manual deposit modal.
 */
async function startDepositPayment({
  paymentType,
  amount,
  bookingId,
  contractId,
  orderInfo,
}) {
  const token = localStorage.getItem("token");
  if (!token) {
    throw new Error("Vui lòng đăng nhập để thanh toán.");
  }

  const normalizedAmount = parseFloat(amount);
  if (!Number.isFinite(normalizedAmount) || normalizedAmount <= 0) {
    throw new Error("Số tiền cọc không hợp lệ.");
  }

  const payload = {
    amount: normalizedAmount,
    payment_type: paymentType,
  };

  if (paymentType === "booking") {
    if (!bookingId) {
      throw new Error("Không xác định được booking để thanh toán.");
    }
    payload.booking_id = bookingId;
  } else if (paymentType === "contract") {
    if (!contractId) {
      throw new Error("Không xác định được hợp đồng để thanh toán.");
    }
    payload.contract_id = contractId;
  }

  const depositResponse = await fetch(`${API_GATEWAY}/api/payments/deposit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const depositData = await depositResponse.json();
  if (!depositResponse.ok) {
    throw new Error(
      depositData.message || "Không thể tạo thông tin thanh toán tiền cọc."
    );
  }

  const paymentId =
    depositData.payment?.id ||
    depositData.payment?._id ||
    depositData.payment_id;
  if (!paymentId) {
    throw new Error("Không nhận được mã thanh toán từ hệ thống.");
  }

  const orderInfoMessage =
    orderInfo ||
    `Thanh toán tiền phòng ${
      paymentType === "booking" ? "đặt phòng" : "hợp đồng"
    }`;

  // Check payment method (vnpay or momo)
  // We need to pass the method to this function or infer it.
  // but we can add it or check the form.
  // However, the backend /api/payments/deposit creates a payment with default method 'vnpay'.
  // We should update the backend to accept method, or update the payment method later.
  
  // Let's assume we pass 'method' to this function.
  // Get payment method (now always vnpay for online payments)
  const vnpayResponse = await fetch(
    `${API_GATEWAY}/api/payments/vnpay/create`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        payment_id: paymentId,
        amount: normalizedAmount,
        order_info: orderInfoMessage,
        return_url: `${window.location.origin}/payment-return`,
      }),
    }
  );

  const vnpayData = await vnpayResponse.json();
  if (!vnpayResponse.ok || !vnpayData.payment_url) {
    throw new Error(
      vnpayData.message || "Không thể tạo đường dẫn thanh toán VNPay."
    );
  }

  // Redirect to VNPAY payment gateway
  window.location.href = vnpayData.payment_url;
}

// Expose helper for booking flow
window.payDepositForBooking = async function payDepositForBooking({
  bookingId,
  amount,
  method
}) {
  return startDepositPayment({
    paymentType: "booking",
    amount,
    bookingId,
    method: method || 'vnpay',
    orderInfo: `Thanh toán tiền phòng đặt phòng ${bookingId}`,
  });
};

// Open Pay Deposit Modal
window.openPayDepositModal = async function openPayDepositModal() {
  const modal = document.getElementById("payDepositModal");
  if (modal) modal.style.display = "block";
  document.getElementById("userDropdown").style.display = "none";
  
  // Reset form
  const form = document.getElementById("payDepositForm");
  if (form) form.reset();
  
  const alert = document.getElementById("payDepositAlert");
  if (alert) {
    alert.style.display = "none";
    alert.className = "alert";
  }
  
  // Load bookings and contracts
  await loadBookingsAndContracts();
  
  // Show/hide fields based on payment type
  const paymentTypeSelect = document.getElementById("depositPaymentType");
  if (paymentTypeSelect) {
    paymentTypeSelect.addEventListener("change", function() {
      const bookingGroup = document.getElementById("bookingIdGroup");
      const contractGroup = document.getElementById("contractIdGroup");
      
      if (this.value === "booking") {
        if (bookingGroup) bookingGroup.style.display = "block";
        if (contractGroup) contractGroup.style.display = "none";
      } else if (this.value === "contract") {
        if (bookingGroup) bookingGroup.style.display = "none";
        if (contractGroup) contractGroup.style.display = "block";
      } else {
        if (bookingGroup) bookingGroup.style.display = "none";
        if (contractGroup) contractGroup.style.display = "none";
      }
    });
  }
};

// Close Pay Deposit Modal
window.closePayDepositModal = function closePayDepositModal() {
  const modal = document.getElementById("payDepositModal");
  if (modal) modal.style.display = "none";
};

// Load bookings and contracts
async function loadBookingsAndContracts() {
  const token = localStorage.getItem("token");
  if (!token) return;
  
  try {
    // Load bookings
    const bookingsResponse = await fetch(`${API_GATEWAY}/api/bookings`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (bookingsResponse.ok) {
      const bookingsData = await bookingsResponse.json();
      const bookings = bookingsData.bookings || [];
      
      const bookingSelect = document.getElementById("depositBookingId");
      if (bookingSelect) {
        bookingSelect.innerHTML = '<option value="">Chọn booking</option>';
        bookings.forEach(booking => {
          if (booking.status === "approved") {
            const option = document.createElement("option");
            option.value = booking.id || booking._id;
            option.textContent = `Booking ${booking.id || booking._id} - ${formatPrice(booking.deposit || 0)}`;
            option.setAttribute("data-deposit", booking.deposit || 0);
            bookingSelect.appendChild(option);
          }
        });
        
        // Auto-fill deposit amount when booking is selected
        bookingSelect.addEventListener("change", function() {
          const selectedOption = this.options[this.selectedIndex];
          const deposit = selectedOption.getAttribute("data-deposit");
          const amountInput = document.getElementById("depositAmount");
          if (amountInput && deposit) {
            amountInput.value = deposit;
          }
        });
      }
    }
    
    // Load contracts
    const contractsResponse = await fetch(`${API_GATEWAY}/api/contracts`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (contractsResponse.ok) {
      const contractsData = await contractsResponse.json();
      const contracts = contractsData.contracts || [];
      
      const contractSelect = document.getElementById("depositContractId");
      if (contractSelect) {
        contractSelect.innerHTML = '<option value="">Chọn hợp đồng</option>';
        contracts.forEach(contract => {
          if (contract.status === "active") {
            const option = document.createElement("option");
            option.value = contract.id || contract._id;
            option.textContent = `Hợp đồng ${contract.id || contract._id} - ${formatPrice(contract.deposit || 0)}`;
            option.setAttribute("data-deposit", contract.deposit || 0);
            contractSelect.appendChild(option);
          }
        });
        
        // Auto-fill deposit amount when contract is selected
        contractSelect.addEventListener("change", function() {
          const selectedOption = this.options[this.selectedIndex];
          const deposit = selectedOption.getAttribute("data-deposit");
          const amountInput = document.getElementById("depositAmount");
          if (amountInput && deposit) {
            amountInput.value = deposit;
          }
        });
      }
    }
  } catch (error) {
    console.error("Error loading bookings/contracts:", error);
  }
}

// Pay bill amount (called from user-bills.js)
window.payBillAmount = async function payBillAmount(billId, amount, orderInfo) {
  const token = localStorage.getItem("token");
  if (!token) {
    alert("Vui lòng đăng nhập");
    return;
  }
  
  try {
    // First create a payment record
    const paymentResponse = await fetch(`${API_GATEWAY}/api/payments`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        bill_id: billId,
        tenant_id: JSON.parse(localStorage.getItem("user") || "{}").id || JSON.parse(localStorage.getItem("user") || "{}")._id,
        amount: amount,
        method: "vnpay",
        payment_date: new Date().toISOString().split("T")[0],
        status: "pending"
      })
    });
    
    if (!paymentResponse.ok) {
      const errorData = await paymentResponse.json();
      throw new Error(errorData.message || "Không thể tạo payment");
    }
    
    const paymentData = await paymentResponse.json();
    const paymentId = paymentData.payment?.id || paymentData.payment?._id || paymentData.payment_id;
    
    // Create VNpay URL
    const vnpayResponse = await fetch(`${API_GATEWAY}/api/payments/vnpay/create`, {
      method: "POST",
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        payment_id: paymentId,
        amount: amount,
        order_info: orderInfo,
        return_url: `${window.location.origin}/payment/vnpay/callback`
      })
    });
    
    if (!vnpayResponse.ok) {
      const errorData = await vnpayResponse.json();
      throw new Error(errorData.message || "Không thể tạo VNpay URL");
    }
    
    const vnpayData = await vnpayResponse.json();
    
    // Redirect to VNpay
    if (vnpayData.payment_url) {
      window.location.href = vnpayData.payment_url;
    } else {
      throw new Error("Không nhận được payment URL");
    }
  } catch (error) {
    console.error("Error creating payment:", error);
    alert(error.message || "Có lỗi xảy ra khi tạo thanh toán");
  }
};

// Handle Pay Deposit Form
document.addEventListener("DOMContentLoaded", function() {
  const payDepositForm = document.getElementById("payDepositForm");
  if (payDepositForm) {
    payDepositForm.addEventListener("submit", async function(e) {
      e.preventDefault();
      
      const token = localStorage.getItem("token");
      if (!token) {
        alert("Vui lòng đăng nhập");
        return;
      }
      
      const alert = document.getElementById("payDepositAlert");
      const paymentType = document.getElementById("depositPaymentType").value;
      const bookingId = document.getElementById("depositBookingId").value;
      const contractId = document.getElementById("depositContractId").value;
      const amount = parseFloat(document.getElementById("depositAmount").value);
      const depositMethod = document.querySelector('input[name="depositMethod"]:checked').value;
      
      // Validation
      if (!paymentType) {
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = "Vui lòng chọn loại thanh toán";
          alert.style.display = "block";
        }
        return;
      }
      
      if (paymentType === "booking" && !bookingId) {
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = "Vui lòng chọn booking";
          alert.style.display = "block";
        }
        return;
      }
      
      if (paymentType === "contract" && !contractId) {
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = "Vui lòng chọn hợp đồng";
          alert.style.display = "block";
        }
        return;
      }
      
      if (!amount || amount <= 0) {
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = "Số tiền phải lớn hơn 0";
          alert.style.display = "block";
        }
        return;
      }
      
      try {
        if (alert) {
          alert.className = "alert alert-success";
          alert.textContent = "Đang chuyển hướng tới VNPay để thanh toán...";
          alert.style.display = "block";
        }

        await startDepositPayment({
          paymentType,
          amount,
          bookingId: paymentType === "booking" ? bookingId : undefined,
          contractId: paymentType === "contract" ? contractId : undefined,
          method: depositMethod,
          orderInfo:
            paymentType === "booking"
              ? `Thanh toán tiền phòng đặt phòng ${bookingId}`
              : `Thanh toán tiền phòng hợp đồng ${contractId}`,
        });
        return;
      } catch (error) {
        console.error("Error processing deposit payment:", error);
        if (alert) {
          alert.className = "alert alert-error";
          alert.textContent = error.message || "Có lỗi xảy ra khi xử lý thanh toán";
          alert.style.display = "block";
        }
      }
    });
  }
});

// Open Payment History Modal
window.openPaymentHistoryModal = async function openPaymentHistoryModal() {
  const modal = document.getElementById("paymentHistoryModal");
  if (modal) modal.style.display = "block";
  document.getElementById("userDropdown").style.display = "none";
  await loadPaymentHistory();
};

// Close Payment History Modal
window.closePaymentHistoryModal = function closePaymentHistoryModal() {
  const modal = document.getElementById("paymentHistoryModal");
  if (modal) modal.style.display = "none";
};

// Load payment history
async function loadPaymentHistory() {
  const listDiv = document.getElementById("paymentHistoryList");
  const token = localStorage.getItem("token");
  
  if (!token) {
    listDiv.innerHTML = '<div style="text-align: center; color: #c33; padding: 20px;">Vui lòng đăng nhập</div>';
    return;
  }
  
  try {
    const response = await fetch(`${API_GATEWAY}/api/payments`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      renderPaymentHistory(data.payments || []);
    } else {
      throw new Error("Không thể tải lịch sử thanh toán");
    }
  } catch (error) {
    listDiv.innerHTML = `<div style="text-align: center; color: #c33; padding: 20px;">${error.message}</div>`;
  }
}

// Render payment history
function renderPaymentHistory(payments) {
  const listDiv = document.getElementById("paymentHistoryList");
  
  if (payments.length === 0) {
    listDiv.innerHTML = `
      <div style="text-align: center; padding: 40px; color: #666;">
        <div style="font-size: 40px; margin-bottom: 10px;">💳</div>
        <p>Bạn chưa có giao dịch thanh toán nào</p>
      </div>
    `;
    return;
  }
  
  listDiv.innerHTML = payments.map(payment => {
    const paymentId = payment._id || payment.id;
    const statusClass = {
      pending: "status-pending",
      completed: "status-completed",
      failed: "status-failed"
    }[payment.status] || "";
    
    const statusText = {
      pending: "Đang chờ",
      completed: "Hoàn thành",
      failed: "Thất bại"
    }[payment.status] || payment.status;
    
    const methodText = {
      cash: "Tiền mặt",
      bank_transfer: "Chuyển khoản",
      vnpay: "VNpay",
      momo: "MoMo"
    }[payment.method] || payment.method;
    
    return `
      <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 15px; border: 1px solid #eee;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px; align-items: start;">
          <div>
            <div style="font-weight: bold; color: #333; font-size: 16px; margin-bottom: 5px;">${paymentId}</div>
            <div style="color: #666; font-size: 13px;">${formatDate(payment.payment_date)}</div>
          </div>
          <div style="
            padding: 6px 12px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: bold;
            ${payment.status === "completed" ? "background: #e8f5e9; color: #2e7d32;" : 
              payment.status === "failed" ? "background: #ffebee; color: #c62828;" : 
              "background: #fff3e0; color: #e65100;"}
          ">
            ${statusText}
          </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 14px;">
          <div>
            <div style="color: #666; margin-bottom: 5px;">Số tiền:</div>
            <div style="font-weight: 600; color: #667eea; font-size: 16px;">${formatPrice(payment.amount || 0)}</div>
          </div>
          <div>
            <div style="color: #666; margin-bottom: 5px;">Phương thức:</div>
            <div style="font-weight: 600; color: #333;">${methodText}</div>
          </div>
        </div>
        
        ${payment.bill_id ? `<div style="margin-top: 10px; font-size: 13px; color: #666;">Hóa đơn: ${payment.bill_id}</div>` : ""}
        ${payment.transaction_id ? `<div style="margin-top: 5px; font-size: 13px; color: #666;">Transaction ID: ${payment.transaction_id}</div>` : ""}
      </div>
    `;
  }).join("");
}

// Handle VNpay callback (when returning from VNpay)
if (window.location.pathname === "/payment/vnpay/callback") {
  const urlParams = new URLSearchParams(window.location.search);
  const responseCode = urlParams.get("vnp_ResponseCode");
  
  if (responseCode === "00") {
    alert("Thanh toán thành công!");
    // Redirect to user home
    window.location.href = "/user-home";
  } else {
    alert("Thanh toán thất bại. Vui lòng thử lại.");
    window.location.href = "/user-home";
  }
}

// Close modals when clicking outside
window.onclick = function(event) {
  if (event.target == document.getElementById("payDepositModal")) {
    closePayDepositModal();
  }
  if (event.target == document.getElementById("paymentHistoryModal")) {
    closePaymentHistoryModal();
  }
};
})();
