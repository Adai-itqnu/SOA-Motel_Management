/**
 * Admin Users Management JavaScript
 */
let currentPage = 1;
let totalPages = 1;
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    // Init layout (this includes auth check)
    if (typeof AdminLayout !== 'undefined') {
        AdminLayout.init();
    } else {
        // Fallback if layout not loaded
        if (!Auth.checkAuth('admin')) return;
    }
    
    // Load users
    loadUsers();
    
    // Search input with debounce
    document.getElementById('searchInput').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 1;
            loadUsers();
        }, 300);
    });
    
    // Filter change events
    document.getElementById('roleFilter').addEventListener('change', () => {
        currentPage = 1;
        loadUsers();
    });
    
    document.getElementById('statusFilter').addEventListener('change', () => {
        currentPage = 1;
        loadUsers();
    });
    
    // Form submit
    document.getElementById('userForm').addEventListener('submit', handleSubmit);
});

async function loadUsers() {
    const search = document.getElementById('searchInput').value.trim();
    const role = document.getElementById('roleFilter').value;
    const status = document.getElementById('statusFilter').value;
    
    let url = `/users?page=${currentPage}&limit=15`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (role) url += `&role=${role}`;
    if (status) url += `&status=${status}`;
    
    try {
        const res = await API.get(url);
        
        if (res.ok) {
            renderUsers(res.data.users);
            totalPages = res.data.pages || 1;
            
            document.getElementById('totalUsers').textContent = res.data.total;
            document.getElementById('currentPage').textContent = res.data.page;
            document.getElementById('totalPages').textContent = totalPages;
            document.getElementById('pageInfo').textContent = `Trang ${res.data.page} / ${totalPages}`;
            
            document.getElementById('prevBtn').disabled = currentPage <= 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages;
        } else {
            console.error('Load users failed:', res.data);
        }
    } catch (error) {
        console.error('Load users error:', error);
    }
}

function renderUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    
    if (!users || users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                    <svg class="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                    </svg>
                    Không tìm thấy người dùng nào
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = users.map(user => `
        <tr class="hover:bg-gray-50 transition">
            <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold">
                        ${(user.fullname || user.username || 'U').charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <p class="font-semibold text-gray-800">${user.fullname || '--'}</p>
                        <p class="text-sm text-gray-500">@${user.username}</p>
                    </div>
                </div>
            </td>
            <td class="px-6 py-4">
                <p class="text-gray-800">${user.email || '--'}</p>
                <p class="text-sm text-gray-500">${user.phone || '--'}</p>
            </td>
            <td class="px-6 py-4 text-gray-600">${user.id_card || '--'}</td>
            <td class="px-6 py-4">
                <span class="px-2.5 py-1 rounded-full text-xs font-medium ${user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}">
                    ${user.role === 'admin' ? 'Admin' : 'User'}
                </span>
            </td>
            <td class="px-6 py-4">
                <span class="px-2.5 py-1 rounded-full text-xs font-medium ${user.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
                    ${user.status === 'active' ? 'Hoạt động' : 'Đã khóa'}
                </span>
            </td>
            <td class="px-6 py-4">
                <div class="flex items-center justify-center gap-2">
                    <button onclick="openEditModal('${user._id}')" class="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition" title="Chỉnh sửa">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                        </svg>
                    </button>
                    ${user.role !== 'admin' ? `
                    <button onclick="toggleStatus('${user._id}', '${user.status}')" class="p-2 ${user.status === 'active' ? 'text-amber-600 hover:bg-amber-50' : 'text-green-600 hover:bg-green-50'} rounded-lg transition" title="${user.status === 'active' ? 'Khóa tài khoản' : 'Kích hoạt'}">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            ${user.status === 'active' 
                                ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>'
                                : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
                            }
                        </svg>
                    </button>
                    <button onclick="openDeleteModal('${user._id}', '${user.fullname || user.username}')" class="p-2 text-red-600 hover:bg-red-50 rounded-lg transition" title="Xóa">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                    </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        loadUsers();
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        loadUsers();
    }
}

async function openEditModal(userId) {
    try {
        const res = await API.get(`/users/${userId}`);
        
        if (res.ok) {
            const user = res.data;
            
            document.getElementById('userId').value = user._id;
            document.getElementById('formUsername').value = user.username || '';
            document.getElementById('formFullname').value = user.fullname || '';
            document.getElementById('formEmail').value = user.email || '';
            document.getElementById('formPhone').value = user.phone || '';
            document.getElementById('formIdCard').value = user.id_card || '';
            document.getElementById('formAddress').value = user.address || '';
            document.getElementById('formRole').value = user.role || 'user';
            document.getElementById('formStatus').value = user.status || 'active';
            
            document.getElementById('modalTitle').textContent = 'Chỉnh sửa người dùng';
            document.getElementById('formError').classList.add('hidden');
            document.getElementById('userModal').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Load user error:', error);
        alert('Không thể tải thông tin người dùng!');
    }
}

function closeModal() {
    document.getElementById('userModal').classList.add('hidden');
    document.getElementById('userForm').reset();
}

async function handleSubmit(e) {
    e.preventDefault();
    
    const userId = document.getElementById('userId').value;
    const data = {
        fullname: document.getElementById('formFullname').value.trim(),
        email: document.getElementById('formEmail').value.trim(),
        phone: document.getElementById('formPhone').value.trim(),
        id_card: document.getElementById('formIdCard').value.trim(),
        address: document.getElementById('formAddress').value.trim(),
        role: document.getElementById('formRole').value,
        status: document.getElementById('formStatus').value
    };
    
    try {
        const res = await API.put(`/users/${userId}`, data);
        
        if (res.ok) {
            closeModal();
            loadUsers();
            alert('Cập nhật thành công!');
        } else {
            document.getElementById('formError').textContent = res.data.message || 'Có lỗi xảy ra!';
            document.getElementById('formError').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Update user error:', error);
        document.getElementById('formError').textContent = 'Lỗi kết nối server!';
        document.getElementById('formError').classList.remove('hidden');
    }
}

async function toggleStatus(userId, currentStatus) {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    const action = newStatus === 'active' ? 'kích hoạt' : 'khóa';
    
    if (!confirm(`Bạn có chắc muốn ${action} tài khoản này?`)) {
        return;
    }
    
    try {
        const res = await API.put(`/users/${userId}/status`, { status: newStatus });
        
        if (res.ok) {
            loadUsers();
        } else {
            alert(res.data.message || 'Có lỗi xảy ra!');
        }
    } catch (error) {
        console.error('Toggle status error:', error);
        alert('Lỗi kết nối server!');
    }
}

function openDeleteModal(userId, userName) {
    document.getElementById('deleteUserId').value = userId;
    document.getElementById('deleteUserName').textContent = userName;
    document.getElementById('deleteModal').classList.remove('hidden');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.add('hidden');
}

async function confirmDelete() {
    const userId = document.getElementById('deleteUserId').value;
    
    try {
        const res = await API.delete(`/users/${userId}`);
        
        if (res.ok) {
            closeDeleteModal();
            loadUsers();
            alert('Xóa thành công!');
        } else {
            alert(res.data.message || 'Không thể xóa người dùng!');
        }
    } catch (error) {
        console.error('Delete user error:', error);
        alert('Lỗi kết nối server!');
    }
}
