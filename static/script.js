// ==================== static/script.js ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log("✅ Adam Cargo System Loaded");

    // إغلاق رسائل التنبيه (Alerts) تلقائياً بعد 5 ثواني
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // تفعيل التلميحات (Tooltips) في Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
