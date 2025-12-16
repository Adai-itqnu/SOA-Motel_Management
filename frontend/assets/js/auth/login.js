/**
 * Login Page JavaScript
 */
document.addEventListener('DOMContentLoaded', () => {
    // Check if already logged in
    if (Auth.isLoggedIn()) {
        verifyAndRedirect();
    }

    // Form submit handler
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
});

// Toggle password visibility
function togglePassword() {
    const passwordInput = document.getElementById('password');
    const eyeIcon = document.getElementById('eyeIcon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"></path>`;
    } else {
        passwordInput.type = 'password';
        eyeIcon.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>`;
    }
}

function setLoading(loading) {
    const btn = document.getElementById('submitBtn');
    const btnText = document.getElementById('btnText');
    const btnLoader = document.getElementById('btnLoader');
    
    btn.disabled = loading;
    btnText.textContent = loading ? 'Đang đăng nhập...' : 'Đăng nhập';
    btnLoader.classList.toggle('hidden', !loading);
}

async function handleLogin(e) {
    e.preventDefault();
    UI.hideError('errorMessage');
    setLoading(true);

    const username = UI.getValue('username');
    const password = document.getElementById('password').value;

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            Auth.setToken(data.token);
            Auth.setUser(data.user);
            redirectByRole(data.user.role);
        } else {
            UI.showError('errorMessage', data.message || 'Đăng nhập thất bại!');
        }
    } catch (error) {
        UI.showError('errorMessage', 'Không thể kết nối đến server. Vui lòng thử lại!');
        console.error('Login error:', error);
    } finally {
        setLoading(false);
    }
}

async function verifyAndRedirect() {
    try {
        const response = await fetch(`${API_URL}/auth/verify`, {
            headers: { 'Authorization': `Bearer ${Auth.getToken()}` }
        });
        
        if (response.ok) {
            const user = Auth.getUser();
            redirectByRole(user.role);
        }
    } catch (error) {
        console.error('Verify error:', error);
    }
}

function redirectByRole(role) {
    if (role === 'admin') {
        window.location.href = '/admin/dashboard.html';
    } else {
        window.location.href = '/user/home.html';
    }
}

