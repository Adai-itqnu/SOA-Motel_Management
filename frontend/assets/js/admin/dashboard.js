/**
 * Admin Dashboard JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    // Init layout (includes auth check)
    if (typeof AdminLayout !== 'undefined') {
        AdminLayout.init();
    } else {
        if (!Auth.checkAuth('admin')) return;
    }
    
    loadDashboardData();
    updateDateTime();
    setInterval(updateDateTime, 60000);
});

function updateDateTime() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('currentDate').textContent = now.toLocaleDateString('vi-VN', options);
    document.getElementById('currentTime').textContent = now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

async function loadDashboardData() {
    try {
        // Load room stats
        const roomsRes = await API.get('/rooms');
        if (roomsRes.ok) {
            const rooms = roomsRes.data.rooms || roomsRes.data || [];
            
            const total = rooms.length;
            const available = rooms.filter(r => r.status === 'available').length;
            const occupied = rooms.filter(r => r.status === 'occupied').length;
            
            // Calculate estimated revenue
            const revenue = rooms
                .filter(r => r.status === 'occupied')
                .reduce((sum, r) => sum + (r.price || 0), 0);
            
            UI.setText('statTotalRooms', total);
            UI.setText('statAvailable', available);
            UI.setText('statOccupied', occupied);
            UI.setText('statRevenue', formatCurrency(revenue));
            
            // Show recent rooms
            renderRecentRooms(rooms.slice(-5).reverse());
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function renderRecentRooms(rooms) {
    const container = document.getElementById('recentRooms');
    if (!container) return;
    
    if (rooms.length === 0) {
        container.innerHTML = '<p class="text-gray-400 text-center py-4">Chưa có phòng nào</p>';
        return;
    }
    
    container.innerHTML = rooms.map(room => `
        <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all">
            <div class="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <span class="text-indigo-600 font-bold">${(room.name || 'P').charAt(0)}</span>
            </div>
            <div class="flex-1">
                <p class="font-medium text-gray-800">${room.name}</p>
                <p class="text-sm text-gray-400">${getRoomTypeLabel(room.room_type)}</p>
            </div>
            <span class="${getStatusClass(room.status)}">${getStatusLabel(room.status)}</span>
        </div>
    `).join('');
}

function getRoomTypeLabel(type) {
    const types = { 'single': 'Phòng đơn', 'double': 'Phòng đôi', 'studio': 'Studio', 'apartment': 'Căn hộ' };
    return types[type] || type || 'Khác';
}

function getStatusLabel(status) {
    const labels = { 'available': 'Trống', 'occupied': 'Đang thuê', 'maintenance': 'Bảo trì' };
    return labels[status] || status;
}

function getStatusClass(status) {
    const classes = {
        'available': 'px-2 py-1 bg-green-100 text-green-700 rounded text-xs',
        'occupied': 'px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs',
        'maintenance': 'px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs'
    };
    return classes[status] || 'px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs';
}

function formatCurrency(amount) {
    if (!amount) return '0 VNĐ';
    return new Intl.NumberFormat('vi-VN').format(amount) + ' VNĐ';
}
