     let allRooms = [];
      let currentRoom = null;
      let currentImageIndex = 0;
      let roomImages = [];

      document.addEventListener("DOMContentLoaded", () => {
        if (!Auth.isLoggedIn()) {
          window.location.href = "/auth/login.html";
          return;
        }

        // Layout.js handles user info, we just need to wait for it
        // then update welcomeName if it exists
        setTimeout(() => {
          const user = Auth.getUser();
          const welcomeName = document.getElementById("welcomeName");
          if (welcomeName && user) {
            welcomeName.textContent =
              user.fullname || user.name || user.username || "User";
          }
        }, 100);

        loadRooms();
        initFilters();
        checkVNPayResult();
      });

      function checkVNPayResult() {
        const params = new URLSearchParams(window.location.search);
        const vnpayStatus = params.get("vnpay");
        if (!vnpayStatus) return;

        const roomId = params.get("room_id");

        // Clean URL
        window.history.replaceState({}, "", "/user/home.html");

        const notice = document.getElementById("vnpayNotice");
        if (!notice) return;

        let cfg = { 
            title: "Thanh toán", 
            msg: "", 
            bgClass: "bg-green-500",
            icon: "check_circle"
        };

        if (vnpayStatus === "success") {
            cfg = {
              title: "Thanh toán thành công!",
              msg: "Giao dịch đã được xác nhận. Phòng đã được giữ cho bạn.",
              bgClass: "bg-green-500",
              icon: "check_circle"
            };
        } else if (vnpayStatus === "cancel") {
            cfg = {
              title: "Thanh toán bị hủy",
              msg: "Bạn đã hủy giao dịch thanh toán.",
              bgClass: "bg-amber-500",
              icon: "warning"
            };
        } else if (vnpayStatus === "pending") {
            cfg = {
              title: "Đang xử lý",
              msg: "Giao dịch đang chờ ngân hàng xác nhận...",
              bgClass: "bg-blue-500",
              icon: "pending"
            };
        } else {
             cfg = {
              title: "Thanh toán thất bại",
              msg: "Có lỗi xảy ra trong quá trình thanh toán.",
              bgClass: "bg-red-500",
              icon: "error"
            };
        }

        // Use horizontal banner style at top center
        notice.className = `fixed top-20 left-1/2 -translate-x-1/2 z-50 max-w-2xl w-full px-4`;
        notice.style.transition = "transform 0.4s ease-out, opacity 0.4s ease-out";
        notice.style.transform = "translateY(-100%)";
        notice.style.opacity = "0";
        
        notice.innerHTML = `
            <div class="flex items-center justify-center gap-3 ${cfg.bgClass} text-white px-6 py-3 rounded-xl shadow-lg">
                <span class="material-symbols-outlined text-xl">${cfg.icon}</span>
                <span class="font-medium">${cfg.title}</span>
                <span class="text-white/90">${cfg.msg}</span>
                <button onclick="this.closest('#vnpayNotice').style.transform='translateY(-100%)'; this.closest('#vnpayNotice').style.opacity='0'; setTimeout(() => this.closest('#vnpayNotice').classList.add('hidden'), 400);" class="ml-4 hover:bg-white/20 rounded-full p-1 transition-colors">
                    <span class="material-symbols-outlined text-lg">close</span>
                </button>
            </div>
        `;
        notice.classList.remove("hidden");
        
        // Slide down animation
        setTimeout(() => {
            notice.style.transform = "translateY(0)";
            notice.style.opacity = "1";
        }, 100);

        // Auto close after 8s
        setTimeout(() => {
            notice.style.transform = "translateY(-100%)";
            notice.style.opacity = "0";
            setTimeout(() => {
                notice.classList.add("hidden");
            }, 400);
        }, 8000);
      }


      function initFilters() {
        const chips = document.querySelectorAll("#filterChips .chip");
        chips.forEach((chip) =>
          chip.addEventListener("click", () => {
            chips.forEach((c) => c.classList.remove("active"));
            chip.classList.add("active");
            filterRooms();
          })
        );
      }

      async function loadRooms() {
        try {
          const res = await API.get("/rooms");
          if (res.ok) {
            allRooms = res.data.rooms || res.data || [];
            filterRooms();
          } else {
            showError("Không thể tải danh sách phòng");
          }
        } catch (error) {
          console.error("Load rooms error:", error);
          showError("Lỗi kết nối server");
        }
      }

      function filterRooms() {
        const activeChip = document.querySelector("#filterChips .chip.active");
        const filter = activeChip ? activeChip.dataset.filter : "all";
        let filtered = allRooms;
        if (filter === "available")
          filtered = filtered.filter((r) => r.status === "available");
        if (filter === "under3")
          filtered = filtered.filter((r) => (r.price || 0) < 3000000);
        if (filter === "3to5")
          filtered = filtered.filter(
            (r) => (r.price || 0) >= 3000000 && (r.price || 0) <= 5000000
          );
        if (filter === "balcony")
          filtered = filtered.filter((r) =>
            (r.amenities || []).includes("balcony")
          );
        renderRooms(filtered);
      }

      function renderRooms(rooms) {
        document.getElementById(
          "roomCount"
        ).textContent = `${rooms.length} phòng`;
        if (!rooms.length) {
          document.getElementById("roomsGrid").innerHTML = `
                        <div class="col-span-full text-center py-12 text-gray-500">Không tìm thấy phòng nào</div>
                    `;
          return;
        }

        document.getElementById("roomsGrid").innerHTML = rooms
          .map((room) => {
            const firstImage =
              room.images?.[0] || "/assets/images/room-placeholder.svg";
            const available = room.status === "available";
            const statusClass = available
              ? "bg-emerald-100 text-emerald-700"
              : "bg-gray-200 text-gray-600";
            const statusText = available ? "Còn trống" : "Đã thuê";
            return `
                        <div onclick="viewRoom('${
                          room._id
                        }')" class="group cursor-pointer flex flex-col rounded-2xl bg-white shadow-sm border border-gray-100 overflow-hidden transition hover:shadow-glow">
                            <div class="relative aspect-[4/3] bg-gray-100 overflow-hidden">
                                <div class="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-105" style="background-image:url('${firstImage}')"></div>
                                <div class="absolute top-3 right-3 ${statusClass} text-xs font-bold px-3 py-1 rounded-full shadow-sm">${statusText}</div>
                            </div>
                            <div class="p-4 flex flex-col gap-3 flex-1">
                                <div class="flex items-center gap-2 text-xs text-gray-500">
                                    <span class="rounded-full bg-gray-100 px-2 py-1">${
                                      room.code || room._id || "---"
                                    }</span>
                                    <span class="rounded-full bg-gray-100 px-2 py-1">Tầng ${
                                      room.floor || "--"
                                    }</span>
                                    <span class="rounded-full bg-gray-100 px-2 py-1">${
                                      room.area || "--"
                                    } m²</span>
                                </div>
                                <div class="flex items-start justify-between gap-3">
                                    <div>
                                        <h3 class="font-black text-lg text-[#1b0e0e] line-clamp-1">${
                                          room.name || "Phòng"
                                        }</h3>
                                        <p class="text-sm text-gray-500 mt-1 line-clamp-2">${
                                          room.description ||
                                          "Phòng mới, sạch sẽ và đầy đủ tiện ích."
                                        }</p>
                                    </div>
                                    <div class="text-right">
                                        <div class="text-2xl font-bold text-primary">${formatCurrency(
                                          room.price
                                        )}</div>
                                        <div class="text-xs text-gray-500">/ tháng</div>
                                    </div>
                                </div>
                                <div class="flex items-center gap-3 text-gray-500 text-sm">
                                    ${(room.amenities || [])
                                      .slice(0, 3)
                                      .map(
                                        (am) =>
                                          `<span class="flex items-center gap-1"><span class="material-symbols-outlined text-[18px] text-primary">${amenityIcon(
                                            am
                                          )}</span>${amenityLabel(am)}</span>`
                                      )
                                      .join("")}
                                </div>
                                <div class="pt-2">
                                    <span class="inline-flex items-center justify-center rounded-lg bg-primary text-white px-4 py-2 text-sm font-semibold transition hover:brightness-105">Xem chi tiết</span>
                                </div>
                            </div>
                        </div>`;
          })
          .join("");
      }

      function amenityLabel(key) {
        const labels = {
          wifi: "Wifi",
          air_conditioner: "Máy lạnh",
          water_heater: "Nước nóng",
          washing_machine: "Máy giặt",
          fridge: "Tủ lạnh",
          kitchen: "Bếp",
          private_wc: "WC riêng",
          balcony: "Ban công",
          parking: "Để xe",
          security: "Bảo vệ",
          elevator: "Thang máy",
          furniture: "Nội thất",
          bed: "Giường",
        };
        return labels[key] || key;
      }

      function amenityIcon(key) {
        const map = {
          wifi: "wifi",
          air_conditioner: "ac_unit",
          water_heater: "water_heater",
          washing_machine: "local_laundry_service",
          fridge: "kitchen",
          kitchen: "restaurant_menu",
          private_wc: "bathtub",
          balcony: "deck",
          parking: "two_wheeler",
          security: "shield",
          elevator: "elevator",
          furniture: "weekend",
          bed: "king_bed",
        };
        return map[key] || "check_circle";
      }

      function viewRoom(roomId) {
        currentRoom = allRooms.find((r) => r._id === roomId);
        if (!currentRoom) return;

        roomImages = currentRoom.images?.length
          ? currentRoom.images
          : ["/assets/images/room-placeholder.svg"];
        currentImageIndex = 0;
        updateCarousel();

        document.getElementById("modalRoomName").textContent = currentRoom.name;
        document.getElementById("modalRoomType").textContent = getRoomTypeLabel(
          currentRoom.room_type
        );
        document.getElementById("modalRoomPrice").textContent = formatCurrency(
          currentRoom.price
        );
        document.getElementById("modalRoomArea").textContent = `${
          currentRoom.area || "--"
        } m²`;
        document.getElementById("modalRoomFloor").textContent = `Tầng ${
          currentRoom.floor || "--"
        }`;
        document.getElementById(
          "modalElectricPrice"
        ).textContent = `${formatNumber(currentRoom.electricity_price || 0)} đ`;
        document.getElementById(
          "modalWaterPrice"
        ).textContent = `${formatNumber(currentRoom.water_price || 0)} đ`;

        const statusEl = document.getElementById("modalRoomStatus");
        if (currentRoom.status === "available") {
          statusEl.className =
            "inline-block px-2 py-1 rounded bg-green-100 text-green-700 text-xs font-bold mb-2";
          statusEl.textContent = "Đang trống";
        } else {
          statusEl.className =
            "inline-block px-2 py-1 rounded bg-gray-200 text-gray-700 text-xs font-bold mb-2";
          statusEl.textContent = "Đã thuê";
        }

        const amenities = currentRoom.amenities || [];
        const labels = {
          wifi: "📶 WiFi",
          air_conditioner: "❄️ Máy lạnh",
          water_heater: "🚿 Nước nóng",
          washing_machine: "🧺 Máy giặt",
          fridge: "🧊 Tủ lạnh",
          kitchen: "🍳 Bếp",
          private_wc: "🚽 WC riêng",
          balcony: "🌇 Ban công",
          parking: "🏍️ Để xe",
          security: "🔒 Bảo vệ",
          elevator: "🛗 Thang máy",
          furniture: "🛋️ Nội thất",
        };
        document.getElementById("amenitiesList").innerHTML = amenities.length
          ? amenities
              .map(
                (a) =>
                  `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-gray-200 bg-gray-50 text-xs font-medium text-gray-600">${
                    labels[a] || a
                  }</span>`
              )
              .join("")
          : '<span class="text-gray-400 text-sm">Không có thông tin</span>';

        document.getElementById("descriptionText").textContent =
          currentRoom.description || "Không có mô tả";

        if (currentRoom.status === "available") {
          const deposit = formatCurrency(currentRoom.deposit || 0);
          document.getElementById("bookingSection").innerHTML = `
                        <div class="bg-gray-50 rounded-xl p-4 mb-3 flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-600">Tiền cọc giữ phòng</p>
                                <p class="text-lg font-bold text-primary">${deposit}</p>
                            </div>
                            <span class="text-xs text-gray-500">Thanh toán qua VNPay</span>
                        </div>
                        <div id="bookingError" class="hidden bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-sm mb-3"></div>
                        <div class="flex gap-3">
                            <button id="bookBtn" onclick="openBookingModal('${currentRoom._id}')" class="flex-1 py-3 px-4 rounded-lg bg-primary hover:bg-primary-hover text-white font-bold text-sm shadow-glow transition active:scale-[0.98]">
                                <span id="bookBtnText">Đặt phòng ngay</span>
                            </button>
                            <button class="px-5 py-3 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-700 font-semibold text-sm">Liên hệ</button>
                        </div>`;
        } else {
          document.getElementById("bookingSection").innerHTML = `
                        <div class="bg-gray-100 rounded-xl p-4 text-center text-gray-500">Phòng này hiện đã có người thuê</div>`;
        }

        document.getElementById("roomModal").classList.remove("hidden");
      }

      function updateCarousel() {
        document.getElementById("carouselImage").src =
          roomImages[currentImageIndex];
        document.getElementById("imageIndicators").innerHTML = roomImages
          .map(
            (_, idx) => `
                    <button onclick="goToImage(${idx})" class="w-2 h-2 rounded-full ${
              idx === currentImageIndex
                ? "bg-white"
                : "bg-white/50 hover:bg-white"
            } transition"></button>
                `
          )
          .join("");
      }
      function prevImage() {
        currentImageIndex =
          (currentImageIndex - 1 + roomImages.length) % roomImages.length;
        updateCarousel();
      }
      function nextImage() {
        currentImageIndex = (currentImageIndex + 1) % roomImages.length;
        updateCarousel();
      }
      function goToImage(idx) {
        currentImageIndex = idx;
        updateCarousel();
      }
      function closeRoomModal() {
        document.getElementById("roomModal").classList.add("hidden");
      }

      // ============== Booking Modal Functions ==============
      let bookingRoomId = null;
      let cachedUserInfo = null;

      async function openBookingModal(roomId) {
        bookingRoomId = roomId;
        const room = allRooms.find((r) => r._id === roomId);
        if (!room) return;

        // Set room info in modal
        document.getElementById("bookingRoomName").textContent = room.name || "Phòng";
        document.getElementById("bookingRoomPrice").textContent = formatCurrency(room.price);
        document.getElementById("bookingDepositAmount").textContent = formatCurrency(room.deposit || 0);

        // Set min date to today
        const today = new Date().toISOString().split("T")[0];
        const dateInput = document.getElementById("bookingCheckInDate");
        dateInput.min = today;
        dateInput.value = today;

        // Load user info
        document.getElementById("bookingFullName").value = "Đang tải...";
        document.getElementById("bookingPhone").value = "Đang tải...";

        try {
          const userRes = await API.get("/users/me");
          if (userRes.ok) {
            cachedUserInfo = userRes.data;
            document.getElementById("bookingFullName").value = cachedUserInfo.fullname || cachedUserInfo.name || cachedUserInfo.username || "";
            document.getElementById("bookingPhone").value = cachedUserInfo.phone || "";
          } else {
            document.getElementById("bookingFullName").value = "Lỗi tải thông tin";
            document.getElementById("bookingPhone").value = "Lỗi tải thông tin";
          }
        } catch (e) {
          console.error("Load user info error:", e);
          document.getElementById("bookingFullName").value = "Lỗi kết nối";
          document.getElementById("bookingPhone").value = "Lỗi kết nối";
        }

        // Reset form state
        document.getElementById("bookingFormError").classList.add("hidden");
        document.getElementById("confirmBookingBtn").disabled = false;
        document.getElementById("confirmBookingBtnText").textContent = "Thanh toán cọc";

        // Show modal
        document.getElementById("bookingModal").classList.remove("hidden");
      }

      function closeBookingModal() {
        document.getElementById("bookingModal").classList.add("hidden");
        bookingRoomId = null;
      }

      // Form submission
      document.addEventListener("DOMContentLoaded", () => {
        const bookingForm = document.getElementById("bookingForm");
        if (bookingForm) {
          bookingForm.addEventListener("submit", handleBookingFormSubmit);
        }
      });

      async function handleBookingFormSubmit(e) {
        e.preventDefault();
        const btn = document.getElementById("confirmBookingBtn");
        const btnText = document.getElementById("confirmBookingBtnText");
        const errorDiv = document.getElementById("bookingFormError");

        // Validate
        const checkInDate = document.getElementById("bookingCheckInDate").value;
        if (!checkInDate) {
          showBookingFormError("Vui lòng chọn ngày nhận phòng");
          return;
        }

        // Check user info
        if (!cachedUserInfo) {
          showBookingFormError("Không thể xác thực người dùng. Vui lòng thử lại.");
          return;
        }

        const hasPhone = cachedUserInfo.phone && cachedUserInfo.phone.trim();
        const hasCCCD = cachedUserInfo.id_card && cachedUserInfo.id_card.trim();
        if (!hasPhone || !hasCCCD) {
          const missing = [];
          if (!hasPhone) missing.push("số điện thoại");
          if (!hasCCCD) missing.push("CCCD/CMND");
          showBookingFormError(`Bạn cần cập nhật ${missing.join(" và ")} trước khi đặt phòng`);
          if (confirm("Đến trang cập nhật thông tin cá nhân?")) {
            window.location.href = "/user/profile.html";
          }
          return;
        }

        // Check room deposit
        const room = allRooms.find((r) => r._id === bookingRoomId);
        if (!room || (room.deposit || 0) <= 0) {
          showBookingFormError("Phòng chưa được cấu hình tiền cọc");
          return;
        }

        // Start payment process
        btn.disabled = true;
        btnText.textContent = "Đang xử lý...";
        errorDiv.classList.add("hidden");

        try {
          btnText.textContent = "Đang chuyển đến VNPay...";
          const paymentRes = await API.post("/vnpay/room-deposit", {
            room_id: bookingRoomId,
            check_in_date: checkInDate
          });

          if (!paymentRes.ok || !paymentRes.data?.payment_url) {
            showBookingFormError(paymentRes.data?.message || "Không thể tạo link thanh toán");
            resetBookingFormBtn();
            return;
          }

          window.location.href = paymentRes.data.payment_url;
        } catch (error) {
          console.error("Booking error:", error);
          showBookingFormError("Lỗi kết nối server");
          resetBookingFormBtn();
        }
      }

      function showBookingFormError(msg) {
        const errorDiv = document.getElementById("bookingFormError");
        if (errorDiv) {
          errorDiv.textContent = msg;
          errorDiv.classList.remove("hidden");
        }
      }

      function resetBookingFormBtn() {
        const btn = document.getElementById("confirmBookingBtn");
        const btnText = document.getElementById("confirmBookingBtnText");
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = "Thanh toán cọc";
      }

      // Keep old functions for backward compatibility
      function showBookingError(msg) {
        const errorDiv = document.getElementById("bookingError");
        if (errorDiv) {
          errorDiv.textContent = msg;
          errorDiv.classList.remove("hidden");
        }
      }
      function resetBookBtn() {
        const btn = document.getElementById("bookBtn");
        const btnText = document.getElementById("bookBtnText");
        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = "Đặt phòng ngay";
      }
      function showError(msg) {
        document.getElementById(
          "roomsGrid"
        ).innerHTML = `<div class="col-span-full text-center py-12 text-red-500">${msg}</div>`;
      }
      function getRoomTypeLabel(type) {
        const types = {
          single: "Phòng đơn",
          double: "Phòng đôi",
          studio: "Studio",
          apartment: "Căn hộ",
        };
        return types[type] || type || "Khác";
      }
      function formatCurrency(amount) {
        return new Intl.NumberFormat("vi-VN").format(amount || 0) + "đ";
      }
      function formatNumber(num) {
        return new Intl.NumberFormat("vi-VN").format(num || 0);
      }
      function logout() {
        Auth.logout();
      }
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeRoomModal();
      });