// ==================== Adam Cargo - Main Script ====================

// منع أي حركة أو تأخير
document.addEventListener('DOMContentLoaded', function() {
    // تثبيت كل العناصر
    var allElements = document.querySelectorAll('*');
    allElements.forEach(function(el) {
        el.style.transition = 'none';
        el.style.animation = 'none';
    });

    // تفعيل كل التلميحات
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // تأكيد الحذف
    var deleteForms = document.querySelectorAll('form[action*="delete"]');
    deleteForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!confirm('هل أنت متأكد من الحذف؟')) {
                e.preventDefault();
            }
        });
    });

    // تحسين حقول التاريخ
    var dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(function(input) {
        if (!input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    });

    // تحسين حقول الشهر
    var monthInputs = document.querySelectorAll('input[type="month"]');
    monthInputs.forEach(function(input) {
        if (!input.value) {
            var now = new Date();
            var month = String(now.getMonth() + 1).padStart(2, '0');
            var year = now.getFullYear();
            input.value = year + '-' + month;
        }
    });

    // تفعيل البحث في الجداول
    var searchInput = document.getElementById('tableSearch');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            var filter = this.value.toLowerCase();
            var table = document.querySelector('table');
            var rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(function(row) {
                var text = row.textContent.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // حساب الصافي تلقائيًا في صفحة إضافة رحلة
    var nauInput = document.querySelector('input[name="nauloon"]');
    var solInput = document.querySelector('input[name="solar"]');
    var expInput = document.querySelector('input[name="expenses"]');
    var dpInput = document.querySelector('input[name="driver_pay"]');

    if (nauInput && solInput && expInput && dpInput) {
        function calculateNet() {
            var nau = parseFloat(nauInput.value) || 0;
            var sol = parseFloat(solInput.value) || 0;
            var exp = parseFloat(expInput.value) || 0;
            var dp = parseFloat(dpInput.value) || 0;
            var net = nau - sol - exp - dp;
            
            var netDisplay = document.getElementById('netDisplay');
            if (netDisplay) {
                netDisplay.textContent = net.toFixed(2);
            }
        }
        
        [nauInput, solInput, expInput, dpInput].forEach(function(input) {
            input.addEventListener('input', calculateNet);
        });
    }

    // تفعيل القوائم المنسدلة
    var dropdowns = document.querySelectorAll('.dropdown-toggle');
    dropdowns.forEach(function(dropdown) {
        dropdown.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
});

// دالة لطباعة الجدول
function printTable() {
    window.print();
}

// دالة لتصدير الجدول كـ Excel
function exportTableToExcel(tableId, fileName) {
    var table = document.getElementById(tableId);
    if (!table) return;
    
    var html = table.outerHTML;
    var blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = fileName + '.xls';
    link.click();
    URL.revokeObjectURL(url);
}

// دالة لتنسيق الأرقام
function formatNumber(num) {
    return num.toLocaleString('ar-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// دالة للتحقق من صحة البيانات
function validateForm(formId) {
    var form = document.getElementById(formId);
    if (!form) return true;
    
    var inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    var isValid = true;
    
    inputs.forEach(function(input) {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// دالة لتحويل التاريخ إلى صيغة عربية
function formatDateArabic(dateString) {
    if (!dateString) return '-';
    var parts = dateString.split('-');
    if (parts.length !== 3) return dateString;
    
    var date = new Date(parts[0], parts[1] - 1, parts[2]);
    return date.toLocaleDateString('ar-EG', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}
