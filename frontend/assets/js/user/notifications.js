/**
 * Simple notification bell toggle for user pages.
 * Currently renders a placeholder list and keeps unread badge synced.
 */
(function () {
  function renderNotifications(listEl, badgeEl, notifications) {
    if (!listEl) return;
    if (!notifications || notifications.length === 0) {
      listEl.innerHTML =
        '<div class="p-4 text-sm text-gray-600">Chưa có thông báo mới</div>';
      if (badgeEl) badgeEl.classList.add("hidden");
      return;
    }

    listEl.innerHTML = notifications
      .map(
        (item) => `
          <div class="px-4 py-3 flex items-start gap-3 hover:bg-gray-50">
            <div class="mt-1 text-primary">
              <span class="material-symbols-outlined text-[18px]">notifications</span>
            </div>
            <div class="flex-1">
              <div class="text-sm font-semibold text-gray-900">${
                item.title || "Thông báo"
              }</div>
              <div class="text-sm text-gray-600">${item.message || ""}</div>
              ${
                item.time
                  ? `<div class="text-xs text-gray-400 mt-1">${item.time}</div>`
                  : ""
              }
            </div>
          </div>
        `
      )
      .join("");

    const unread = notifications.filter((n) => !n.read).length;
    if (badgeEl) {
      if (unread > 0) {
        badgeEl.textContent = unread > 9 ? "9+" : unread;
        badgeEl.classList.remove("hidden");
      } else {
        badgeEl.classList.add("hidden");
      }
    }
  }

  function initNotifications() {
    const bell = document.getElementById("notifBell");
    const dropdown = document.getElementById("notifDropdown");
    const list = document.getElementById("notifList");
    const badge = document.getElementById("notifBadge");

    if (!bell || !dropdown) return;

    const notifications = [];
    renderNotifications(list, badge, notifications);

    const hide = () => dropdown.classList.add("hidden");
    const toggle = (e) => {
      e?.stopPropagation();
      dropdown.classList.toggle("hidden");
    };

    bell.addEventListener("click", toggle);

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target) && !bell.contains(e.target)) {
        hide();
      }
    });

    // Hide on escape key for accessibility
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hide();
    });
  }

  window.initNotifications = initNotifications;
  document.addEventListener("DOMContentLoaded", initNotifications);
})();
