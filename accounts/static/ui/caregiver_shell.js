document.addEventListener('DOMContentLoaded', () => {
    // 1. Tooltips for collapsed sidebar
    // Initialize tooltips only if Bootstrap is loaded
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl, {
                placement: 'right',
                trigger: 'hover',
                boundary: 'window'
            });
        });

        // Hide tooltips when sidebar expands
        const sidebar = document.getElementById('shell-sidebar');
        if (sidebar) {
            sidebar.addEventListener('mouseenter', () => {
                tooltipList.forEach(t => t.hide());
                tooltipList.forEach(t => t.disable());
            });
            sidebar.addEventListener('mouseleave', () => {
                tooltipList.forEach(t => t.enable());
            });
        }
    }

    // 2. Mobile Offcanvas Behavior
    const mobileToggle = document.getElementById('mobile-toggle');
    const sidebar = document.getElementById('shell-sidebar');
    
    // We create a simple dark backdrop for mobile
    let backdrop = null;

    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.add('offcanvas-show');
            
            // Create backdrop if it doesn't exist
            if (!backdrop) {
                backdrop = document.createElement('div');
                backdrop.className = 'offcanvas-backdrop fade show';
                backdrop.style.zIndex = '1035';
                document.body.appendChild(backdrop);
                
                backdrop.addEventListener('click', () => {
                    sidebar.classList.remove('offcanvas-show');
                    backdrop.remove();
                    backdrop = null;
                });
            }
        });
    }

    // 3. Optional: Pin/Unpin (Not strictly required by prompt, but good to have)
    // If we wanted to add a pin button inside the sidebar, we could toggle 'sidebar-pinned' class
    // and store it in localStorage here.
});
