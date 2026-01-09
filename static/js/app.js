/**
 * JavaScript للنظام المحاسبي
 */

// متغيرات عامة
const API_BASE = '/api';
let currentUser = null;

// تهيئة التطبيق
document.addEventListener('DOMContentLoaded', function() {
    // التحقق من تسجيل الدخول
    checkAuth();
    
    // تهيئة المكونات
    initSidebar();
    initForms();
    initDataTables();
    initCharts();
    
    // إضافة معالج للأخطاء العامة
    window.addEventListener('error', handleGlobalError);
});

// وظائف المصادقة
function checkAuth() {
    // التحقق من وجود مستخدم مسجل دخول
    fetch('/api/auth/check')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                currentUser = data.user;
                updateUserInfo();
            } else {
                // إعادة التوجيه لصفحة تسجيل الدخول
                window.location.href = '/login';
            }
        })
        .catch(error => {
            console.error('Auth check failed:', error);
            window.location.href = '/login';
        });
}

function updateUserInfo() {
    // تحديث معلومات المستخدم في الواجهة
    const userElements = document.querySelectorAll('.user-name, .user-role');
    userElements.forEach(el => {
        if (el.classList.contains('user-name')) {
            el.textContent = currentUser.full_name;
        } else if (el.classList.contains('user-role')) {
            el.textContent = currentUser.role;
        }
    });
}

// وظائف الشريط الجانبي
function initSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const menuItems = sidebar.querySelectorAll('.menu-item');
    
    // تحديد العنصر النشط
    const currentPath = window.location.pathname;
    menuItems.forEach(item => {
        const link = item.querySelector('a');
        if (link.getAttribute('href') === currentPath) {
            item.classList.add('active');
        }
    });
    
    // إضافة تفاعل للقوائم المنسدلة
    const dropdowns = sidebar.querySelectorAll('.has-dropdown');
    dropdowns.forEach(dropdown => {
        dropdown.addEventListener('click', function(e) {
            if (!e.target.classList.contains('dropdown-toggle')) return;
            e.preventDefault();
            this.classList.toggle('open');
        });
    });
}

// وظائف النماذج
function initForms() {
    // إضافة التحقق من الصحة للنماذج
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                showAlert('الرجاء ملء جميع الحقول المطلوبة بشكل صحيح', 'error');
            }
        });
    });
    
    // تهيئة منتقي التواريخ
    const datePickers = document.querySelectorAll('.datepicker');
    datePickers.forEach(picker => {
        flatpickr(picker, {
            dateFormat: "Y-m-d",
            locale: "ar",
            allowInput: true,
            disableMobile: true
        });
    });
    
    // تهيئة منتقي الأرقام
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('change', function() {
            this.value = parseFloat(this.value).toFixed(2);
        });
    });
}

// وظائف الجداول
function initDataTables() {
    const tables = document.querySelectorAll('.data-table');
    tables.forEach(table => {
        if (table.id) {
            $(`#${table.id}`).DataTable({
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/ar.json'
                },
                pageLength: 25,
                responsive: true,
                order: []
            });
        }
    });
}

function initCharts() {
    // تهيئة الرسوم البيانية إذا كانت موجودة
    const chartCanvases = document.querySelectorAll('canvas[data-chart]');
    chartCanvases.forEach(canvas => {
        const chartType = canvas.getAttribute('data-chart-type') || 'line';
        const chartData = JSON.parse(canvas.getAttribute('data-chart-data') || '{}');
        
        if (Object.keys(chartData).length > 0) {
            renderChart(canvas, chartType, chartData);
        }
    });
}

function renderChart(canvas, type, data) {
    const ctx = canvas.getContext('2d');
    
    const chart = new Chart(ctx, {
        type: type,
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    rtl: true
                }
            }
        }
    });
    
    return chart;
}

// وظائف API
async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE}${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        credentials: 'include'
    };
    
    if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.message || 'حدث خطأ في الخادم');
        }
        
        return result;
    } catch (error) {
        console.error('API Request failed:', error);
        showAlert(error.message, 'error');
        throw error;
    }
}

// وظائف التنبيهات
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // إضافة التنبيه إلى بداية الصفحة
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    // إزالة التنبيه تلقائياً بعد 5 ثواني
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// معالجة الأخطاء العامة
function handleGlobalError(event) {
    console.error('Global error:', event.error);
    showAlert('حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى', 'error');
}

// وظائف المساعدة
function formatCurrency(amount, currency = 'SAR') {
    return new Intl.NumberFormat('ar-SA', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ar-SA');
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// تصدير الوظائف العامة
window.AccountingSystem = {
    apiRequest,
    showAlert,
    formatCurrency,
    formatDate,
    initCharts,
    renderChart
};
