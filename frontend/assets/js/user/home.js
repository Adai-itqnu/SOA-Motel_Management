/**
 * User Home Page JavaScript
 */
document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.checkAuth("user")) return;

  // Show VNPay result notice (if redirected back from VNPay)
  renderVnpayResultNotice();

  // Load user info
  loadUserInfo();

  // Auto-open edit profile modal when redirected from other pages
  const params = new URLSearchParams(window.location.search);
  if (params.get("edit") === "1") {
    // Remove param to avoid reopening on refresh
    params.delete("edit");
    const newQs = params.toString();
    const newUrl = `${window.location.pathname}${newQs ? `?${newQs}` : ""}${
      window.location.hash || ""
    }`;
    window.history.replaceState({}, "", newUrl);
    openProfileModal();
  }

  // No contracts service wired yet
  renderCurrentRoomPlaceholder();
});

function setVnpayNotice(noticeEl, { title, message, cls, baseInfo }) {
  // Use horizontal banner style at top of page
  const bgClass = cls.includes('green') ? 'bg-green-500' : 
                  cls.includes('red') ? 'bg-red-500' : 
                  cls.includes('amber') ? 'bg-amber-500' : 
                  cls.includes('indigo') ? 'bg-indigo-500' : 'bg-gray-500';
  
  const iconName = cls.includes('green') ? 'check_circle' : 
                   cls.includes('red') ? 'error' : 
                   cls.includes('amber') ? 'warning' : 
                   cls.includes('indigo') ? 'pending' : 'info';

  noticeEl.className = `fixed top-20 left-1/2 -translate-x-1/2 z-50 max-w-2xl w-full px-4`;
  noticeEl.style.transition = "transform 0.4s ease-out, opacity 0.4s ease-out";
  noticeEl.style.transform = "translateY(-100%)";
  noticeEl.style.opacity = "0";
  
  noticeEl.innerHTML = `
    <div class="flex items-center justify-center gap-3 ${bgClass} text-white px-6 py-3 rounded-xl shadow-lg">
      <span class="material-symbols-outlined text-xl">${iconName}</span>
      <span class="font-medium">${title}</span>
      <span class="text-white/90">${message}</span>
      <button id="vnpayNoticeClose" class="ml-4 hover:bg-white/20 rounded-full p-1 transition-colors">
        <span class="material-symbols-outlined text-lg">close</span>
      </button>
    </div>
  `;
  noticeEl.classList.remove("hidden");

  // Trigger slide-down animation
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      noticeEl.style.transform = "translateY(0)";
      noticeEl.style.opacity = "1";
    });
  });

  document.getElementById("vnpayNoticeClose")?.addEventListener("click", () => {
    // Slide out animation before hiding
    noticeEl.style.transform = "translateY(-100%)";
    noticeEl.style.opacity = "0";
    setTimeout(() => {
      noticeEl.classList.add("hidden");
    }, 400);
  });

  // Auto-hide after 8 seconds
  setTimeout(() => {
    if (!noticeEl.classList.contains("hidden")) {
      noticeEl.style.transform = "translateY(-100%)";
      noticeEl.style.opacity = "0";
      setTimeout(() => {
        noticeEl.classList.add("hidden");
      }, 400);
    }
  }, 8000);
}

async function pollVnpayVerification({
  noticeEl,
  paymentId,
  bookingId,
  baseInfo,
}) {
  if (!paymentId) return;

  const maxAttempts = 6; // ~12s total
  const delayMs = 2000;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    // If user closed the notice, stop polling.
    if (noticeEl.classList.contains("hidden")) return;

    const res = await API.get(
      `/payments/vnpay/verify/${encodeURIComponent(paymentId)}`
    );
    if (res.ok) {
      const status = res.data?.status;
      if (status === "completed") {
        setVnpayNotice(noticeEl, {
          title: "Thanh toán thành công",
          message:
            "Giao dịch đã được xác minh với VNPay. Trạng thái booking sẽ được cập nhật ngay.",
          cls: "bg-green-50 border border-green-200 text-green-800",
          baseInfo,
        });
        return;
      }

      // If QueryDR confirms failure codes, show failed.
      const txnStatus = res.data?.transaction_status;
      const rspCode = res.data?.provider_response_code;
      if (txnStatus && txnStatus !== "00") {
        setVnpayNotice(noticeEl, {
          title: "Thanh toán chưa được xác nhận",
          message: `Trạng thái giao dịch: ${txnStatus}. Vui lòng thử lại hoặc liên hệ admin.`,
          cls: "bg-red-50 border border-red-200 text-red-800",
          baseInfo,
        });
        return;
      }
      if (rspCode && rspCode !== "00") {
        setVnpayNotice(noticeEl, {
          title: "Thanh toán chưa được xác nhận",
          message: `Mã phản hồi: ${rspCode}. Vui lòng thử lại hoặc liên hệ admin.`,
          cls: "bg-red-50 border border-red-200 text-red-800",
          baseInfo,
        });
        return;
      }
    }

    // Still pending; update message with attempt counter.
    setVnpayNotice(noticeEl, {
      title: "Đang xác minh thanh toán",
      message: `Hệ thống đang xác minh giao dịch với VNPay (lần ${attempt}/${maxAttempts})...`,
      cls: "bg-indigo-50 border border-indigo-200 text-indigo-800",
      baseInfo,
    });

    await new Promise((r) => setTimeout(r, delayMs));
  }

  // Timeout: keep pending but give a clear next step.
  setVnpayNotice(noticeEl, {
    title: "Đang xác minh thanh toán",
    message:
      "Chưa xác minh được trong thời gian ngắn. Vui lòng đợi thêm và tải lại, hoặc kiểm tra lại trong lịch sử đặt phòng.",
    cls: "bg-indigo-50 border border-indigo-200 text-indigo-800",
    baseInfo,
  });
}

function renderVnpayResultNotice() {
  const noticeEl = document.getElementById("vnpayNotice");
  if (!noticeEl) return;

  const params = new URLSearchParams(window.location.search);
  const vnpay = params.get("vnpay");
  if (!vnpay) return;

  const paymentId = params.get("payment_id") || "";
  const bookingId = params.get("booking_id") || "";
  const code = params.get("code") || "";

  const baseInfo = [
    bookingId ? `Booking: ${bookingId}` : null,
    paymentId ? `Payment: ${paymentId}` : null,
  ]
    .filter(Boolean)
    .join(" • ");

  let title = "";
  let message = "";
  let cls = "";

  if (vnpay === "success") {
    title = "Thanh toán thành công";
    message =
      "Hệ thống đã ghi nhận kết quả. Nếu trạng thái chưa cập nhật ngay, vui lòng đợi vài giây rồi tải lại.";
    cls = "bg-green-50 border border-green-200 text-green-800";
  } else if (vnpay === "pending") {
    title = "Đang xác minh thanh toán";
    message =
      "Hệ thống đang xác minh giao dịch với VNPay. Vui lòng đợi vài giây rồi tải lại để cập nhật trạng thái.";
    cls = "bg-indigo-50 border border-indigo-200 text-indigo-800";
  } else if (vnpay === "cancel") {
    title = "Bạn đã hủy thanh toán";
    message = "Bạn có thể thực hiện thanh toán lại bất cứ lúc nào.";
    cls = "bg-amber-50 border border-amber-200 text-amber-800";
  } else if (vnpay === "failed") {
    title = "Thanh toán thất bại";
    message = code ? `Mã lỗi: ${code}. Vui lòng thử lại.` : "Vui lòng thử lại.";
    cls = "bg-red-50 border border-red-200 text-red-800";
  } else if (vnpay === "error") {
    title = "Có lỗi khi xử lý thanh toán";
    message = code ? `Mã lỗi: ${code}. Vui lòng thử lại.` : "Vui lòng thử lại.";
    cls = "bg-red-50 border border-red-200 text-red-800";
  } else {
    // Unknown status
    title = "Trạng thái thanh toán";
    message = "Đã nhận kết quả từ VNPay.";
    cls = "bg-gray-50 border border-gray-200 text-gray-800";
  }

  setVnpayNotice(noticeEl, { title, message, cls, baseInfo });

  // Remove params so refresh doesn't show the notice again
  ["vnpay", "payment_id", "booking_id", "code"].forEach((k) =>
    params.delete(k)
  );
  const newQs = params.toString();
  const newUrl = `${window.location.pathname}${newQs ? `?${newQs}` : ""}${
    window.location.hash || ""
  }`;
  window.history.replaceState({}, "", newUrl);

  // Professional touch: auto-verify when pending.
  if (vnpay === "pending" && paymentId) {
    pollVnpayVerification({ noticeEl, paymentId, bookingId, baseInfo });
  }
}

function loadUserInfo() {
  const user = Auth.getUser();
  const displayName = user.fullname || user.name || user.username || "User";

  UI.setText("userName", displayName);
  UI.setText("welcomeName", displayName);
  document.getElementById("userAvatar").textContent = displayName
    .charAt(0)
    .toUpperCase();
  UI.setText("profileName", displayName);
  UI.setText("profileEmail", user.email || "--");
  UI.setText("profilePhone", user.phone || "--");
  UI.setText("profileIdCard", user.id_card || "--");
}

// Keep legacy function name used in older HTML (if any)
function editProfile() {
  openProfileModal();
}

function openProfileModal() {
  const modal = document.getElementById("profileModal");
  if (!modal) return;
  UI.hideError("profileFormError");
  UI.hideError("profileFormSuccess");
  modal.classList.remove("hidden");
  loadProfileIntoForm();
}

function closeProfileModal() {
  document.getElementById("profileModal")?.classList.add("hidden");
}

async function loadProfileIntoForm() {
  // Use server truth if possible
  const res = await API.get("/users/me");
  const user = res.ok ? res.data : Auth.getUser();

  // Sync local storage user info
  if (res.ok && user) {
    const existing = Auth.getUser();
    Auth.setUser({ ...existing, ...user });
    loadUserInfo();
  }

  const fullnameEl = document.getElementById("profileFullnameInput");
  const phoneEl = document.getElementById("profilePhoneInput");
  const idCardEl = document.getElementById("profileIdCardInput");
  const addressEl = document.getElementById("profileAddressInput");

  if (fullnameEl) fullnameEl.value = user?.fullname || "";
  if (phoneEl) phoneEl.value = user?.phone || "";
  if (idCardEl) idCardEl.value = user?.id_card || "";
  if (addressEl) addressEl.value = user?.address || "";
}

async function handleProfileSubmit(e) {
  e.preventDefault();
  UI.hideError("profileFormError");
  UI.hideError("profileFormSuccess");

  const fullname = UI.getValue("profileFullnameInput");
  const phone = UI.getValue("profilePhoneInput");
  const idCard = UI.getValue("profileIdCardInput");
  const address = UI.getValue("profileAddressInput");

  if (!fullname) {
    UI.showError("profileFormError", "Vui lòng nhập họ và tên.");
    return;
  }

  const submitBtn = document.getElementById("profileSaveBtn");
  if (submitBtn) submitBtn.disabled = true;

  const res = await API.put("/users/me", {
    fullname,
    phone,
    id_card: idCard,
    address,
  });

  if (!res.ok) {
    UI.showError(
      "profileFormError",
      res.data?.message || "Không thể cập nhật thông tin."
    );
    if (submitBtn) submitBtn.disabled = false;
    return;
  }

  UI.showError("profileFormSuccess", "Cập nhật thành công!");
  const updated = res.data?.user;
  if (updated) {
    const existing = Auth.getUser();
    Auth.setUser({ ...existing, ...updated });
    loadUserInfo();
  }

  if (submitBtn) submitBtn.disabled = false;
  // Close shortly to confirm UX
  setTimeout(() => closeProfileModal(), 600);
}

// Wire profile modal events
document.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("profileCloseBtn")
    ?.addEventListener("click", closeProfileModal);
  document
    .getElementById("profileCancelBtn")
    ?.addEventListener("click", closeProfileModal);
  document
    .getElementById("profileForm")
    ?.addEventListener("submit", handleProfileSubmit);

  const modal = document.getElementById("profileModal");
  modal?.addEventListener("click", (e) => {
    if (e.target && e.target.id === "profileModal") closeProfileModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeProfileModal();
  });
});

// Expose for menu.js
window.openProfileModal = openProfileModal;

function renderCurrentRoomPlaceholder() {
  UI.setHTML(
    "currentRoom",
    `
        <div class="text-center py-8">
            <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
            </svg>
            <p class="text-gray-500 mb-4">Chưa có thông tin phòng đang thuê</p>
            <a href="./rooms.html" class="inline-block px-6 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors">
                Xem phòng trống
            </a>
        </div>
    `
  );
}
