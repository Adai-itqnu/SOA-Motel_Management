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

// Open My Bills Modal
window.openMyBillsModal = async function openMyBillsModal() {
  const modal = document.getElementById("myBillsModal");
  if (modal) modal.style.display = "block";
  document.getElementById("userDropdown").style.display = "none";
  await loadMyBills();
};

// Close My Bills Modal
window.closeMyBillsModal = function closeMyBillsModal() {
  const modal = document.getElementById("myBillsModal");
  if (modal) modal.style.display = "none";
};

// Load my bills
async function loadMyBills() {
  const listDiv = document.getElementById("myBillsList");
  const token = localStorage.getItem("token");
  
  if (!token) {
    listDiv.innerHTML = '<div style="text-align: center; color: #c33; padding: 20px;">Vui lòng đăng nhập</div>';
    return;
  }
  
  try {
    const response = await fetch(`${API_GATEWAY}/api/bills`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      renderMyBills(data.bills || []);
    } else {
      throw new Error("Không thể tải danh sách hóa đơn");
    }
  } catch (error) {
    listDiv.innerHTML = `<div style="text-align: center; color: #c33; padding: 20px;">${error.message}</div>`;
  }
}

// Render my bills
function renderMyBills(bills) {
  const listDiv = document.getElementById("myBillsList");
  
  if (bills.length === 0) {
    listDiv.innerHTML = `
      <div style="text-align: center; padding: 40px; color: #666;">
        <div style="font-size: 40px; margin-bottom: 10px;">🧾</div>
        <p>Bạn chưa có hóa đơn nào</p>
      </div>
    `;
    return;
  }
  
  listDiv.innerHTML = bills.map(bill => {
    const billId = bill._id || bill.id;
    const statusClass = bill.status === "paid" ? "status-paid" : "status-unpaid";
    const statusText = bill.status === "paid" ? "Đã thanh toán" : "Chưa thanh toán";
    
    // Calculate remaining amount (if needed)
    const totalAmount = bill.total_amount || 0;
    
    return `
      <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 15px; border: 1px solid #eee;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 15px; align-items: start;">
          <div>
            <div style="font-weight: bold; color: #333; font-size: 18px; margin-bottom: 5px;">Hóa đơn ${billId}</div>
            <div style="color: #666; font-size: 14px;">Tháng: ${bill.month || "N/A"}</div>
          </div>
          <div style="
            padding: 6px 12px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: bold;
            ${bill.status === "paid" ? "background: #e8f5e9; color: #2e7d32;" : "background: #fff3e0; color: #e65100;"}
          ">
            ${statusText}
          </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; font-size: 14px;">
          <div>
            <div style="color: #666; margin-bottom: 5px;">Phòng:</div>
            <div style="font-weight: 600; color: #333;">${bill.room_id || "N/A"}</div>
          </div>
          <div>
            <div style="color: #666; margin-bottom: 5px;">Tổng tiền:</div>
            <div style="font-weight: 600; color: #667eea; font-size: 16px;">${formatPrice(totalAmount)}</div>
          </div>
        </div>
        
        <div style="background: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
          <div style="font-weight: 600; margin-bottom: 10px; color: #333;">Chi tiết:</div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">
            <div>Giá phòng: ${formatPrice(bill.room_price || 0)}</div>
            <div>Điện: ${bill.electric_start || 0} → ${bill.electric_end || 0} (${((bill.electric_end || 0) - (bill.electric_start || 0)) * (bill.electric_price || 0)} VNĐ)</div>
            <div>Nước: ${bill.water_start || 0} → ${bill.water_end || 0} (${((bill.water_end || 0) - (bill.water_start || 0)) * (bill.water_price || 0)} VNĐ)</div>
            <div>Giá điện: ${formatPrice(bill.electric_price || 0)}/kWh</div>
            <div>Giá nước: ${formatPrice(bill.water_price || 0)}/m³</div>
          </div>
        </div>
        
        ${bill.status !== "paid" ? `
          <div style="text-align: right;">
            <button onclick="payBill('${billId}')" style="
              padding: 10px 20px; 
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
              color: white; 
              border: none; 
              border-radius: 6px; 
              cursor: pointer;
              font-weight: 600;
            ">
              Thanh toán
            </button>
          </div>
        ` : ""}
      </div>
    `;
  }).join("");
}

// Pay bill (redirect to payment)
function payBill(billId) {
  // This will be handled by user-payments.js
  if (window.payBillAmount) {
    // Get bill details first
    const token = localStorage.getItem("token");
    fetch(`${API_GATEWAY}/api/bills/${billId}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(res => res.json())
    .then(data => {
      const bill = data.bill || data;
      if (window.payBillAmount) {
        window.payBillAmount(billId, bill.total_amount || 0, `Thanh toán hóa đơn ${billId}`);
      }
    })
    .catch(err => {
      console.error("Error loading bill:", err);
      alert("Không thể tải thông tin hóa đơn");
    });
  } else {
    alert("Chức năng thanh toán đang được phát triển");
  }
}

// Close modal when clicking outside
window.onclick = function(event) {
  if (event.target == document.getElementById("myBillsModal")) {
    closeMyBillsModal();
  }
};
})();

