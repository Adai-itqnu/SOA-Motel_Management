/**
 * User header avatar menu
 * - Click avatar/name to open a small actions modal
 * - Actions: edit profile, monthly bills/payments
 */

(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function openModal() {
    const modal = $("userActionsModal");
    if (!modal) return;
    modal.classList.remove("hidden");
  }

  function closeModal() {
    const modal = $("userActionsModal");
    if (!modal) return;
    modal.classList.add("hidden");
  }

  function onBackdropClick(e) {
    if (e.target && e.target.id === "userActionsModal") {
      closeModal();
    }
  }

  function goToHomeEdit() {
    if (window.location.pathname.endsWith("/user/home.html")) {
      if (typeof window.openProfileModal === "function") {
        window.openProfileModal();
        return;
      }
    }
    window.location.href = "/user/home.html?edit=1";
  }

  function goToBills() {
    window.location.href = "/user/bookings.html";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = $("userMenuButton");
    const modal = $("userActionsModal");

    if (!btn || !modal) return;

    btn.addEventListener("click", openModal);
    modal.addEventListener("click", onBackdropClick);

    $("userActionsClose")?.addEventListener("click", closeModal);

    $("userActionsEditProfile")?.addEventListener("click", () => {
      closeModal();
      goToHomeEdit();
    });

    $("userActionsBills")?.addEventListener("click", () => {
      closeModal();
      goToBills();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  });

  // Expose for pages that want to close programmatically
  window.closeUserActionsModal = closeModal;
})();
