/**
 * User Rooms Page JavaScript
 * - View available rooms
 * - Hold room by paying deposit via VNPay (no admin approval)
 */
document.addEventListener("DOMContentLoaded", () => {
  if (!Auth.checkAuth("user")) return;
  loadUserInfo();
  renderVnpayResultNotice();
  loadMyReservedRooms();
  loadRooms();

  // Room detail modal events
  document
    .getElementById("roomDetailClose")
    ?.addEventListener("click", closeRoomDetailModal);
  document
    .getElementById("roomDetailPrev")
    ?.addEventListener("click", () => stepRoomDetailImage(-1));
  document
    .getElementById("roomDetailNext")
    ?.addEventListener("click", () => stepRoomDetailImage(1));

  const modal = document.getElementById("roomDetailModal");
  modal?.addEventListener("click", (e) => {
    if (e.target && e.target.id === "roomDetailModal") closeRoomDetailModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeRoomDetailModal();
  });
});

function loadUserInfo() {
  const user = Auth.getUser();
  const displayName = user.fullname || user.name || user.username || "User";
  UI.setText("userName", displayName);
  const avatarEl = document.getElementById("userAvatar");
  if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();
}

function logout() {
  Auth.logout();
}

function setVnpayNotice(noticeEl, { title, message, cls, baseInfo }) {
  noticeEl.className = `rounded-2xl p-4 mb-6 ${cls}`;
  noticeEl.innerHTML = `
    <div class="flex items-start gap-3">
      <div class="flex-1">
        <div class="font-bold">${title}</div>
        <div class="text-sm mt-1">${message}</div>
        ${
          baseInfo
            ? `<div class="text-xs mt-2 opacity-80">${baseInfo}</div>`
            : ""
        }
      </div>
      <button id="vnpayNoticeClose" class="text-sm font-semibold underline">Đóng</button>
    </div>
  `;
  noticeEl.classList.remove("hidden");
  document.getElementById("vnpayNoticeClose")?.addEventListener("click", () => {
    noticeEl.classList.add("hidden");
  });
}

async function pollVnpayVerification({
  noticeEl,
  paymentId,
  roomId,
  baseInfo,
}) {
  if (!paymentId) return;

  const maxAttempts = 6;
  const delayMs = 2000;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (noticeEl.classList.contains("hidden")) return;

    const res = await API.get(
      `/payments/vnpay/verify/${encodeURIComponent(paymentId)}`
    );
    if (res.ok) {
      const status = res.data?.status;
      if (status === "completed") {
        setVnpayNotice(noticeEl, {
          title: "Giữ phòng thành công",
          message:
            "Giao dịch đã được xác minh với VNPay. Phòng đã được giữ cho bạn.",
          cls: "bg-green-50 border border-green-200 text-green-800",
          baseInfo,
        });
        await loadMyReservedRooms();
        await loadRooms();
        return;
      }

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

    setVnpayNotice(noticeEl, {
      title: "Đang xác minh thanh toán",
      message: `Hệ thống đang xác minh giao dịch với VNPay (lần ${attempt}/${maxAttempts})...`,
      cls: "bg-indigo-50 border border-indigo-200 text-indigo-800",
      baseInfo,
    });

    await new Promise((r) => setTimeout(r, delayMs));
  }

  setVnpayNotice(noticeEl, {
    title: "Đang xác minh thanh toán",
    message:
      "Chưa xác minh được trong thời gian ngắn. Vui lòng đợi thêm và tải lại trang, hoặc kiểm tra trong lịch sử thanh toán.",
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
  const roomId = params.get("room_id") || "";
  const code = params.get("code") || "";

  const baseInfo = [
    roomId ? `Room: ${roomId}` : null,
    paymentId ? `Payment: ${paymentId}` : null,
  ]
    .filter(Boolean)
    .join(" • ");

  let title = "";
  let message = "";
  let cls = "";

  if (vnpay === "success") {
    title = "Thanh toán thành công";
    message = "Hệ thống đã ghi nhận. Phòng sẽ được giữ cho bạn.";
    cls = "bg-green-50 border border-green-200 text-green-800";
  } else if (vnpay === "pending") {
    title = "Đang xác minh thanh toán";
    message =
      "Hệ thống đang xác minh giao dịch với VNPay. Vui lòng đợi vài giây.";
    cls = "bg-indigo-50 border border-indigo-200 text-indigo-800";
  } else if (vnpay === "cancel") {
    title = "Bạn đã hủy thanh toán";
    message =
      "Phòng đã được nhả. Bạn có thể thực hiện lại thanh toán để giữ phòng.";
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
    title = "Trạng thái thanh toán";
    message = "Đã nhận kết quả từ VNPay.";
    cls = "bg-gray-50 border border-gray-200 text-gray-800";
  }

  setVnpayNotice(noticeEl, { title, message, cls, baseInfo });

  ["vnpay", "payment_id", "room_id", "code"].forEach((k) => params.delete(k));
  const newQs = params.toString();
  const newUrl = `${window.location.pathname}${newQs ? `?${newQs}` : ""}${
    window.location.hash || ""
  }`;
  window.history.replaceState({}, "", newUrl);

  if (vnpay === "pending" && paymentId) {
    pollVnpayVerification({ noticeEl, paymentId, roomId, baseInfo });
  }
}

function formatStatus(status) {
  if (status === "available")
    return { label: "Trống", cls: "bg-green-100 text-green-700" };
  if (status === "reserved")
    return { label: "Đang giữ", cls: "bg-amber-100 text-amber-700" };
  if (status === "occupied")
    return { label: "Đang thuê", cls: "bg-gray-100 text-gray-700" };
  if (status === "maintenance")
    return { label: "Bảo trì", cls: "bg-red-100 text-red-700" };
  return { label: status || "--", cls: "bg-gray-100 text-gray-700" };
}

async function loadRooms() {
  UI.hide("roomsError");
  UI.show("roomsLoading");
  UI.hide("roomsEmpty");
  UI.hide("roomsGrid");

  const res = await API.get("/rooms/available");
  UI.hide("roomsLoading");

  if (!res.ok) {
    UI.showError(
      "roomsError",
      res.data?.message || "Không thể tải danh sách phòng"
    );
    return;
  }

  const rooms = res.data?.rooms || [];
  if (rooms.length === 0) {
    UI.show("roomsEmpty");
    return;
  }

  const grid = document.getElementById("roomsGrid");
  grid.innerHTML = rooms
    .map((room) => {
      const status = formatStatus(room.status);
      const price = UI.formatCurrency(room.price || 0);
      const deposit = UI.formatCurrency(room.deposit || 0);
      const desc = (room.description || "").trim();

      const area = Number(room.area_m2 || 0);
      const amenities = Array.isArray(room.amenities) ? room.amenities : [];
      const img =
        Array.isArray(room.images) && room.images.length
          ? room.images[0]
          : null;
      const imgUrl = img?.data_b64
        ? `data:${img.content_type || "image/jpeg"};base64,${img.data_b64}`
        : "";

      return `
        <div class="bg-white rounded-2xl shadow-lg p-6 flex flex-col cursor-pointer" onclick="openRoomDetailModal('${escapeHtml(
          room._id
        )}')">
          ${
            imgUrl
              ? `<div class="mb-4">
                  <img src="${imgUrl}" alt="${escapeHtml(
                  room.name || room._id
                )}" class="w-full h-40 object-cover rounded-xl" />
                </div>`
              : ""
          }
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-lg font-bold text-gray-800">${escapeHtml(
                room.name || room._id
              )}</h3>
              <p class="text-sm text-gray-500">Loại: ${escapeHtml(
                room.room_type || "--"
              )}</p>
            </div>
            <span class="px-3 py-1 rounded-full text-xs font-semibold ${
              status.cls
            }">${status.label}</span>
          </div>

          <div class="mt-3 flex flex-wrap gap-2 text-xs">
            ${
              area
                ? `<span class="px-2 py-1 bg-gray-100 text-gray-700 rounded-full">${area} m²</span>`
                : ""
            }
            ${amenities
              .slice(0, 6)
              .map(
                (a) =>
                  `<span class="px-2 py-1 bg-gray-100 text-gray-700 rounded-full">${escapeHtml(
                    amenityLabel(a)
                  )}</span>`
              )
              .join("")}
          </div>

          <div class="mt-4 space-y-2 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-gray-500">Giá thuê/tháng</span>
              <span class="font-semibold text-indigo-600">${price}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-gray-500">Tiền cọc</span>
              <span class="font-semibold text-gray-800">${deposit}</span>
            </div>
          </div>

          ${
            desc
              ? `<p class="mt-4 text-sm text-gray-600 line-clamp-3">${escapeHtml(
                  desc
                )}</p>`
              : ""
          }

          <div class="mt-6">
            <button
              class="w-full px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors"
              onclick="event.stopPropagation(); reserveRoomVnpay('${escapeHtml(
                room._id
              )}')"
            >
              Giữ phòng (thanh toán cọc)
            </button>
          </div>
        </div>
      `;
    })
    .join("");

  UI.show("roomsGrid");
}

// ============== ROOM DETAIL MODAL ==============
let roomDetailImages = [];
let roomDetailIndex = 0;

function toImgUrl(img) {
  if (!img || !img.data_b64) return "";
  return `data:${img.content_type || "image/jpeg"};base64,${img.data_b64}`;
}

async function openRoomDetailModal(roomId) {
  const modal = document.getElementById("roomDetailModal");
  if (!modal) return;

  // Reset UI
  UI.setText("roomDetailTitle", "Chi tiết phòng");
  UI.setText("roomDetailSubtitle", roomId || "--");
  UI.setText("roomDetailPrice", "--");
  UI.setText("roomDetailDeposit", "--");
  UI.setHTML("roomDetailAmenities", "");
  UI.setText("roomDetailDescription", "--");

  roomDetailImages = [];
  roomDetailIndex = 0;
  updateRoomDetailImage();

  modal.classList.remove("hidden");

  const res = await API.get(`/rooms/public/${encodeURIComponent(roomId)}`);
  if (!res.ok) {
    UI.setText(
      "roomDetailDescription",
      res.data?.message || "Không thể tải chi tiết phòng."
    );
    return;
  }

  const room = res.data || {};
  UI.setText("roomDetailTitle", room.name || room._id || "Chi tiết phòng");
  const subtitleParts = [];
  if (room.room_type) subtitleParts.push(`Loại: ${room.room_type}`);
  const area = Number(room.area_m2 || 0);
  if (area) subtitleParts.push(`${area} m²`);
  UI.setText("roomDetailSubtitle", subtitleParts.join(" • ") || "--");

  UI.setText("roomDetailPrice", UI.formatCurrency(room.price || 0));
  UI.setText("roomDetailDeposit", UI.formatCurrency(room.deposit || 0));

  const amenities = Array.isArray(room.amenities) ? room.amenities : [];
  UI.setHTML(
    "roomDetailAmenities",
    amenities.length
      ? amenities
          .map(
            (a) =>
              `<span class="px-2 py-1 bg-gray-100 text-gray-700 rounded-full text-xs">${escapeHtml(
                amenityLabel(a)
              )}</span>`
          )
          .join("")
      : `<span class="text-sm text-gray-500">--</span>`
  );

  const desc = (room.description || "").trim();
  UI.setText("roomDetailDescription", desc || "--");

  roomDetailImages = Array.isArray(room.images) ? room.images : [];
  roomDetailIndex = 0;
  updateRoomDetailImage();
}

function closeRoomDetailModal() {
  document.getElementById("roomDetailModal")?.classList.add("hidden");
}

function stepRoomDetailImage(delta) {
  const n = roomDetailImages.length;
  if (n <= 1) return;
  roomDetailIndex = (roomDetailIndex + delta + n) % n;
  updateRoomDetailImage();
}

function updateRoomDetailImage() {
  const imgEl = document.getElementById("roomDetailImage");
  const emptyEl = document.getElementById("roomDetailImageEmpty");
  const prevBtn = document.getElementById("roomDetailPrev");
  const nextBtn = document.getElementById("roomDetailNext");

  const n = roomDetailImages.length;
  const hasImages = n > 0;

  if (imgEl) imgEl.classList.toggle("hidden", !hasImages);
  if (emptyEl) emptyEl.classList.toggle("hidden", hasImages);

  if (prevBtn) prevBtn.disabled = n <= 1;
  if (nextBtn) nextBtn.disabled = n <= 1;

  if (hasImages && imgEl) {
    imgEl.src = toImgUrl(roomDetailImages[roomDetailIndex]);
  }
}

async function reserveRoomVnpay(roomId) {
  const noticeEl = document.getElementById("vnpayNotice");
  if (noticeEl) noticeEl.classList.add("hidden");

  const res = await API.post("/payments/vnpay/room-deposit/create", {
    room_id: roomId,
  });
  if (!res.ok) {
    if (noticeEl) {
      setVnpayNotice(noticeEl, {
        title: "Không thể giữ phòng",
        message: res.data?.message || "Vui lòng thử lại.",
        cls: "bg-red-50 border border-red-200 text-red-800",
        baseInfo: roomId ? `Room: ${roomId}` : "",
      });
    } else {
      alert(res.data?.message || "Không thể giữ phòng");
    }
    return;
  }

  const paymentUrl = res.data?.payment_url;
  if (!paymentUrl) {
    if (noticeEl) {
      setVnpayNotice(noticeEl, {
        title: "Không thể tạo thanh toán",
        message: "Thiếu payment_url từ server.",
        cls: "bg-red-50 border border-red-200 text-red-800",
        baseInfo: roomId ? `Room: ${roomId}` : "",
      });
    }
    return;
  }

  window.location.href = paymentUrl;
}

async function loadMyReservedRooms() {
  const box = document.getElementById("myReserved");
  const list = document.getElementById("myReservedList");
  if (!box || !list) return;

  const res = await API.get("/rooms/my-reservations");
  if (!res.ok) {
    box.classList.add("hidden");
    return;
  }

  const rooms = res.data?.rooms || [];
  if (!rooms.length) {
    box.classList.add("hidden");
    return;
  }

  list.innerHTML = rooms.map(renderReservedRoomCard).join("");
  box.classList.remove("hidden");
}

function renderReservedRoomCard(room) {
  const price = UI.formatCurrency(room.price || 0);
  const deposit = UI.formatCurrency(room.deposit || 0);
  const area = Number(room.area_m2 || 0);
  const amenities = Array.isArray(room.amenities) ? room.amenities : [];
  const img =
    Array.isArray(room.images) && room.images.length ? room.images[0] : null;
  const imgUrl = img?.data_b64
    ? `data:${img.content_type || "image/jpeg"};base64,${img.data_b64}`
    : "";

  const resStatus = room.reservation_status || "pending_payment";
  const badge =
    resStatus === "paid"
      ? { label: "Đã cọc", cls: "bg-green-100 text-green-700" }
      : { label: "Chờ xác minh", cls: "bg-amber-100 text-amber-700" };

  return `
    <div class="bg-gray-50 rounded-2xl p-4">
      ${
        imgUrl
          ? `<img src="${imgUrl}" alt="${escapeHtml(
              room.name || room._id
            )}" class="w-full h-32 object-cover rounded-xl mb-3" />`
          : ""
      }
      <div class="flex items-start justify-between gap-2">
        <div>
          <div class="font-bold text-gray-800">${escapeHtml(
            room.name || room._id
          )}</div>
          <div class="text-sm text-gray-500">${escapeHtml(
            room.room_type || "--"
          )}${area ? ` • ${area} m²` : ""}</div>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-semibold ${
          badge.cls
        }">${badge.label}</span>
      </div>
      <div class="mt-3 text-sm">
        <div class="flex items-center justify-between"><span class="text-gray-500">Giá</span><span class="font-semibold text-gray-800">${price}</span></div>
        <div class="flex items-center justify-between"><span class="text-gray-500">Cọc</span><span class="font-semibold text-gray-800">${deposit}</span></div>
      </div>
      <div class="mt-3 flex flex-wrap gap-2 text-xs">
        ${amenities
          .slice(0, 8)
          .map(
            (a) =>
              `<span class="px-2 py-1 bg-white text-gray-700 rounded-full">${escapeHtml(
                amenityLabel(a)
              )}</span>`
          )
          .join("")}
      </div>
    </div>
  `;
}

function amenityLabel(a) {
  switch (String(a || "").toLowerCase()) {
    case "wifi":
      return "WiFi";
    case "air_conditioner":
      return "Máy lạnh";
    case "water_heater":
      return "Máy nước nóng";
    case "washing_machine":
      return "Máy giặt";
    case "fridge":
      return "Tủ lạnh";
    case "kitchen":
      return "Bếp";
    case "private_wc":
      return "WC riêng";
    case "balcony":
      return "Ban công";
    case "parking":
      return "Chỗ để xe";
    default:
      return a || "--";
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
