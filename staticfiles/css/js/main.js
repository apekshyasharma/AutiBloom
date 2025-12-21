/**
 * Modal Alert System for AutiBloom
 * Converts Django messages to Bootstrap modal dialogs
 */

document.addEventListener('DOMContentLoaded', function() {
    const messageData = document.getElementById('message-data');
    
    if (!messageData) return;

    try {
        const messages = JSON.parse(messageData.textContent);
        
        if (messages && messages.length > 0) {
            // Display first message in queue
            const message = messages[0];
            showAlert(message.type, message.message);
        }
    } catch (error) {
        console.error('Error parsing messages:', error);
    }
});

/**
 * Display alert modal with title and message
 * @param {string} type - Message type: 'success', 'error', 'warning', 'info'
 * @param {string} message - Message text to display
 */
function showAlert(type, message) {
    const modalTitle = document.getElementById('alertModalLabel');
    const modalBody = document.getElementById('alertModalBody');
    const modalHeader = document.getElementById('alertModalHeader');
    
    // Set title based on type
    const titles = {
        'success': '✓ Success',
        'error': '✗ Error',
        'warning': '⚠ Warning',
        'info': 'ℹ Information'
    };
    
    const colors = {
        'success': '#10b981',
        'error': '#dc2626',
        'warning': '#f59e0b',
        'info': '#3b82f6'
    };
    
    modalTitle.textContent = titles[type] || 'Message';
    modalBody.textContent = message;
    modalHeader.style.borderBottom = `3px solid ${colors[type]}`;
    
    const alertModal = new bootstrap.Modal(document.getElementById('alertModal'));
    alertModal.show();
}

/**
 * Expose showAlert globally for manual triggers
 */
window.showAlert = showAlert;