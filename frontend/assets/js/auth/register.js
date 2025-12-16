/**
 * Register Page JavaScript
 */
let currentStep = 1;

document.addEventListener("DOMContentLoaded", () => {
  // Form submit handler
  document
    .getElementById("registerForm")
    .addEventListener("submit", handleRegister);

  // Password strength checker
  document
    .getElementById("password")
    .addEventListener("input", onPasswordInput);

  // Password match checker
  document
    .getElementById("confirmPassword")
    .addEventListener("input", onConfirmPasswordInput);

  // Toggle password visibility
  const togglePasswordBtn = document.getElementById("togglePassword");
  const passwordInput = document.getElementById("password");
  const togglePasswordIcon = document.getElementById("togglePasswordIcon");

  if (togglePasswordBtn && passwordInput && togglePasswordIcon) {
    togglePasswordBtn.addEventListener("click", () => {
      const showing = passwordInput.type === "text";
      passwordInput.type = showing ? "password" : "text";
      togglePasswordIcon.textContent = showing
        ? "visibility_off"
        : "visibility";
      togglePasswordBtn.setAttribute(
        "aria-label",
        showing ? "Hiển thị mật khẩu" : "Ẩn mật khẩu"
      );
    });
  }
});

// Step Navigation
function nextStep() {
  const name = UI.getValue("name");
  const email = UI.getValue("email");
  const phone = UI.getValue("phone");

  if (!name || !email || !phone) {
    alert("Vui lòng điền đầy đủ thông tin!");
    return;
  }

  if (!Validate.email(email)) {
    alert("Email không hợp lệ!");
    return;
  }

  if (!Validate.phone(phone)) {
    alert("Số điện thoại không hợp lệ!");
    return;
  }

  currentStep = 2;
  document.getElementById("formStep1").classList.add("hidden");
  document.getElementById("formStep2").classList.remove("hidden");
  document.getElementById("step1").classList.remove("step-active");
  document.getElementById("step1").classList.add("step-completed");
  document.getElementById("step1").innerHTML = "✓";
  document.getElementById("step2").classList.add("step-active");
  document
    .getElementById("step2")
    .classList.remove("bg-gray-200", "text-gray-500");
  document.getElementById("line1").classList.add("bg-green-500");
  document.getElementById("line1").classList.remove("bg-gray-200");
}

function prevStep() {
  currentStep = 1;
  document.getElementById("formStep1").classList.remove("hidden");
  document.getElementById("formStep2").classList.add("hidden");
  document.getElementById("step1").classList.add("step-active");
  document.getElementById("step1").classList.remove("step-completed");
  document.getElementById("step1").innerHTML = "1";
  document.getElementById("step2").classList.remove("step-active");
  document
    .getElementById("step2")
    .classList.add("bg-gray-200", "text-gray-500");
  document.getElementById("line1").classList.remove("bg-green-500");
  document.getElementById("line1").classList.add("bg-gray-200");
}

// Password Strength
function onPasswordInput() {
  const password = this.value;
  const strength = checkPasswordStrength(password);
  updateStrengthIndicator(strength);
}

function checkPasswordStrength(password) {
  let strength = 0;
  if (password.length >= 6) strength++;
  if (password.length >= 8) strength++;
  if (/[A-Z]/.test(password)) strength++;
  if (/[0-9]/.test(password)) strength++;
  if (/[^A-Za-z0-9]/.test(password)) strength++;
  return Math.min(strength, 4);
}

function updateStrengthIndicator(strength) {
  const colors = [
    "bg-gray-200",
    "bg-red-500",
    "bg-yellow-500",
    "bg-blue-500",
    "bg-green-500",
  ];
  const texts = ["Nhập mật khẩu", "Yếu", "Trung bình", "Khá", "Mạnh"];
  const textColors = [
    "text-gray-400",
    "text-red-500",
    "text-yellow-500",
    "text-blue-500",
    "text-green-500",
  ];

  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById("str" + i);
    el.className = "h-1 flex-1 rounded transition-all duration-300";
    el.classList.add(i <= strength ? colors[strength] : "bg-gray-200");
  }

  const strText = document.getElementById("strText");
  strText.textContent = texts[strength];
  strText.className = "text-xs mt-1 " + textColors[strength];
}

// Password Match
function onConfirmPasswordInput() {
  const password = document.getElementById("password").value;
  const matchError = document.getElementById("matchError");

  if (this.value && this.value !== password) {
    matchError.classList.remove("hidden");
  } else {
    matchError.classList.add("hidden");
  }
}

// Form Submit
function setLoading(loading) {
  const btn = document.getElementById("submitBtn");
  const btnText = document.getElementById("btnText");
  const btnLoader = document.getElementById("btnLoader");

  btn.disabled = loading;
  btnText.textContent = loading ? "Đang đăng ký..." : "Đăng ký";
  btnLoader.classList.toggle("hidden", !loading);
}

async function handleRegister(e) {
  e.preventDefault();
  UI.hideError("errorMessage");

  const password = document.getElementById("password").value;
  const confirmPassword = document.getElementById("confirmPassword").value;

  if (password !== confirmPassword) {
    UI.showError("errorMessage", "Mật khẩu xác nhận không khớp!");
    return;
  }

  if (password.length < 6) {
    UI.showError("errorMessage", "Mật khẩu phải có ít nhất 6 ký tự!");
    return;
  }

  if (!document.getElementById("terms").checked) {
    UI.showError("errorMessage", "Vui lòng đồng ý với điều khoản dịch vụ!");
    return;
  }

  setLoading(true);

  const formData = {
    fullname: UI.getValue("name"),
    email: UI.getValue("email"),
    phone: UI.getValue("phone"),
    username: UI.getValue("username"),
    password: password,
  };

  try {
    const response = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });

    const data = await response.json();

    if (response.ok) {
      alert("Đăng ký thành công! Vui lòng đăng nhập.");
      window.location.href = "/auth/login.html";
    } else {
      UI.showError("errorMessage", data.message || "Đăng ký thất bại!");
    }
  } catch (error) {
    UI.showError(
      "errorMessage",
      "Không thể kết nối đến server. Vui lòng thử lại!"
    );
    console.error("Register error:", error);
  } finally {
    setLoading(false);
  }
}
