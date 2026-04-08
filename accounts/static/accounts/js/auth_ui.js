document.addEventListener('DOMContentLoaded', function () {

    // 1. Password Toggle
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');
    togglePasswordButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            const inputId = this.getAttribute('data-target');
            const input = document.getElementById(inputId);
            const icon = this.querySelector('i');

            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        });
    });

    // 2. Form Submission Spinner
    const forms = document.querySelectorAll('form.needs-spinner');
    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            const btn = this.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                btn.classList.add('submitting');
                btn.disabled = true;
                // Allow form submission to proceed
            }
        });
    });

    // 3. Admin Modal Data Linking
    const confirmModal = document.getElementById('confirmationModal');
    if (confirmModal) {
        confirmModal.addEventListener('show.bs.modal', event => {
            // Button that triggered the modal
            const button = event.relatedTarget;
            // Extract info from data-bs-* attributes
            const actionUrl = button.getAttribute('data-action-url');
            const actionName = button.getAttribute('data-action-name');
            const username = button.getAttribute('data-username');
            const confirmBtnClass = button.getAttribute('data-confirm-class') || 'btn-primary';

            // Update the modal's content.
            const modalTitle = confirmModal.querySelector('.modal-title');
            const modalBody = confirmModal.querySelector('.modal-body-text');
            const modalForm = confirmModal.querySelector('form');
            const modalConfirmBtn = confirmModal.querySelector('.btn-confirm');

            modalTitle.textContent = `Confirm: ${actionName}`;
            modalBody.textContent = `Are you sure you want to ${actionName.toLowerCase()} the clinician "${username}"?`;

            modalForm.action = actionUrl;

            // Reset classes
            modalConfirmBtn.className = 'btn btn-confirm';
            modalConfirmBtn.classList.add(confirmBtnClass);
            modalConfirmBtn.textContent = actionName;
        });
    }
});
