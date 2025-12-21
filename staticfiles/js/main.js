/**
 * AutiBloom - Main JavaScript Enhancement Module
 * 
 * Lightweight, progressive enhancements for Django server-rendered application
 * - No external dependencies, no frameworks
 * - Gracefully degrades if JavaScript is disabled
 * - Healthcare-grade UX patterns
 */

(function() {
    'use strict';

    // =====================================================
    // 1. AUTO-DISMISS BOOTSTRAP ALERT MESSAGES
    // =====================================================
    
    /**
     * Auto-dismiss alerts after 5 seconds
     * Provides visual feedback while preventing alert fatigue
     */
    function initAutoDismissAlerts() {
        const alerts = document.querySelectorAll('.alert:not(.alert-dismissible)');
        
        alerts.forEach(alert => {
            // Only auto-dismiss success and info alerts
            if (alert.classList.contains('alert-success') || 
                alert.classList.contains('alert-info')) {
                
                setTimeout(() => {
                    // Fade out effect
                    alert.style.transition = 'opacity 300ms ease-out';
                    alert.style.opacity = '0';
                    
                    // Remove from DOM after fade
                    setTimeout(() => {
                        alert.remove();
                    }, 300);
                }, 5000);
            }
        });
    }

    // =====================================================
    // 2. PREVENT DOUBLE FORM SUBMISSION
    // =====================================================
    
    /**
     * Disable submit buttons after click to prevent double submission
     * Shows loading state with visual feedback
     */
    function initFormSubmissionPrevention() {
        const forms = document.querySelectorAll('form');
        
        forms.forEach(form => {
            form.addEventListener('submit', function(event) {
                const submitButtons = this.querySelectorAll('button[type="submit"]');
                
                submitButtons.forEach(button => {
                    // Store original text
                    const originalText = button.textContent;
                    const originalHTML = button.innerHTML;
                    
                    // Disable button
                    button.disabled = true;
                    button.style.opacity = '0.7';
                    button.style.cursor = 'not-allowed';
                    button.setAttribute('aria-busy', 'true');
                    
                    // Show loading indicator
                    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
                    
                    // Restore button if form submission fails (e.g., validation error)
                    // Re-enable after short delay to allow response processing
                    setTimeout(() => {
                        button.disabled = false;
                        button.style.opacity = '1';
                        button.style.cursor = 'pointer';
                        button.setAttribute('aria-busy', 'false');
                        button.innerHTML = originalHTML;
                    }, 3000);
                });
            });
        });
    }

    // =====================================================
    // 3. PASSWORD VISIBILITY TOGGLE
    // =====================================================
    
    /**
     * Toggle password field visibility
     * Supports optional password visibility toggle buttons
     * HTML hooks: data-toggle-password attribute on button
     */
    function initPasswordVisibilityToggle() {
        // Look for password toggle buttons
        const toggleButtons = document.querySelectorAll('[data-toggle-password]');
        
        toggleButtons.forEach(button => {
            const targetId = button.getAttribute('data-toggle-password');
            const passwordInput = document.getElementById(targetId);
            
            if (!passwordInput) return;
            
            button.addEventListener('click', function(event) {
                event.preventDefault();
                
                const isPassword = passwordInput.type === 'password';
                
                // Toggle input type
                passwordInput.type = isPassword ? 'text' : 'password';
                
                // Update button appearance and aria-label
                const icon = button.querySelector('i');
                const label = button.querySelector('span');
                
                if (isPassword) {
                    // Showing password
                    if (icon) {
                        icon.classList.remove('bi-eye-slash');
                        icon.classList.add('bi-eye');
                    }
                    if (label) label.textContent = 'Hide password';
                    button.setAttribute('aria-label', 'Hide password');
                    button.setAttribute('aria-pressed', 'true');
                } else {
                    // Hiding password
                    if (icon) {
                        icon.classList.remove('bi-eye');
                        icon.classList.add('bi-eye-slash');
                    }
                    if (label) label.textContent = 'Show password';
                    button.setAttribute('aria-label', 'Show password');
                    button.setAttribute('aria-pressed', 'false');
                }
            });
        });
    }

    // =====================================================
    // 4. DASHBOARD CARD HOVER MICRO-INTERACTIONS
    // =====================================================
    
    /**
     * Add subtle hover effects to dashboard cards
     * Smooth elevation and shadow transitions
     * Progressive enhancement - works with CSS classes
     */
    function initCardHoverInteractions() {
        const cards = document.querySelectorAll('.card');
        
        cards.forEach(card => {
            // Add interactive class for enhanced hover effects
            card.classList.add('interactive-card');
            
            // Track mouse position for subtle parallax effect (optional)
            card.addEventListener('mouseenter', function() {
                this.style.transition = 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)';
                this.style.transform = 'translateY(-8px) scale(1.01)';
                this.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.15)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0) scale(1)';
                this.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
            });
            
            // Touch support for mobile devices
            card.addEventListener('touchstart', function() {
                this.style.transition = 'all 300ms cubic-bezier(0.4, 0, 0.2, 1)';
                this.style.transform = 'translateY(-4px)';
            });
            
            card.addEventListener('touchend', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }

    // =====================================================
    // 5. BUTTON HOVER STATE ENHANCEMENTS
    // =====================================================
    
    /**
     * Enhanced button interactions with smooth transitions
     * Works with Bootstrap button classes
     */
    function initButtonEnhancements() {
        const buttons = document.querySelectorAll('.btn');
        
        buttons.forEach(button => {
            // Add smooth transitions
            button.style.transition = 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)';
            
            // Prevent double-click selection
            button.style.userSelect = 'none';
            
            // Visual feedback on click
            button.addEventListener('mousedown', function() {
                this.style.transform = 'scale(0.98)';
            });
            
            button.addEventListener('mouseup', function() {
                this.style.transform = 'scale(1)';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1)';
            });
        });
    }

    // =====================================================
    // 6. FORM INPUT FOCUS ENHANCEMENT
    // =====================================================
    
    /**
     * Enhanced form input interactions
     * Smooth focus states and visual feedback
     */
    function initFormInputEnhancements() {
        const inputs = document.querySelectorAll('.form-control, .form-select');
        
        inputs.forEach(input => {
            input.addEventListener('focus', function() {
                this.style.transition = 'all 150ms ease-out';
                // Focus state is handled by CSS, just ensure smooth transition
            });
            
            input.addEventListener('blur', function() {
                // Add validation feedback if needed
                if (this.classList.contains('is-invalid')) {
                    this.setAttribute('aria-invalid', 'true');
                } else if (this.value.trim()) {
                    this.setAttribute('aria-invalid', 'false');
                }
            });
        });
    }

    // =====================================================
    // 7. ACCESSIBILITY ENHANCEMENTS
    // =====================================================
    
    /**
     * Improve accessibility for keyboard navigation
     * Skip links and focus management
     */
    function initAccessibilityEnhancements() {
        // Add focus visible support for better keyboard navigation
        document.body.classList.add('js-enabled');
        
        // Trap focus in modals if present
        const modals = document.querySelectorAll('[role="dialog"]');
        modals.forEach(modal => {
            const focusableElements = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            
            if (focusableElements.length > 0) {
                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];
                
                modal.addEventListener('keydown', function(event) {
                    if (event.key === 'Tab') {
                        if (event.shiftKey) {
                            if (document.activeElement === firstElement) {
                                event.preventDefault();
                                lastElement.focus();
                            }
                        } else {
                            if (document.activeElement === lastElement) {
                                event.preventDefault();
                                firstElement.focus();
                            }
                        }
                    }
                });
            }
        });
    }

    // =====================================================
    // 8. RESPONSIVE NAVBAR ENHANCEMENT
    // ===================================================== 
    
    /**
     * Close navbar on link click (mobile)
     * Improve mobile UX
     */
    function initNavbarEnhancements() {
        const navbarToggler = document.querySelector('.navbar-toggler');
        const navbarCollapse = document.querySelector('.navbar-collapse');
        const navLinks = document.querySelectorAll('.navbar-collapse .nav-link');
        
        if (navbarToggler && navbarCollapse) {
            navLinks.forEach(link => {
                link.addEventListener('click', function() {
                    // Close navbar if it's open
                    if (navbarCollapse.classList.contains('show')) {
                        navbarToggler.click();
                    }
                });
            });
        }
    }

    // =====================================================
    // 9. SCROLL-TO-TOP BUTTON (Optional Enhancement)
    // =====================================================
    
    /**
     * Show scroll-to-top button when user scrolls down
     * Smooth scroll back to top
     */
    function initScrollToTop() {
        // This is an optional enhancement
        // Only init if scroll-to-top button exists
        const scrollButton = document.querySelector('[data-scroll-to-top]');
        if (!scrollButton) return;
        
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                scrollButton.style.display = 'block';
                scrollButton.style.opacity = '1';
            } else {
                scrollButton.style.opacity = '0';
                setTimeout(() => {
                    scrollButton.style.display = 'none';
                }, 300);
            }
        });
        
        scrollButton.addEventListener('click', function(event) {
            event.preventDefault();
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // =====================================================
    // 10. INITIALIZATION & DOM READY
    // =====================================================
    
    /**
     * Initialize all enhancements when DOM is ready
     */
    function init() {
        // Check if DOM is already loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeEnhancements);
        } else {
            initializeEnhancements();
        }
    }
    
    function initializeEnhancements() {
        // Progressive enhancement initialization
        try {
            initAutoDismissAlerts();
            initFormSubmissionPrevention();
            initPasswordVisibilityToggle();
            initCardHoverInteractions();
            initButtonEnhancements();
            initFormInputEnhancements();
            initAccessibilityEnhancements();
            initNavbarEnhancements();
            initScrollToTop();
            
            // Mark as initialized
            console.log('AutiBloom JavaScript enhancements loaded successfully');
        } catch (error) {
            // Fail gracefully - don't break page if JS error occurs
            console.error('Error initializing AutiBloom enhancements:', error);
        }
    }
    
    // Initialize when script loads
    init();

})();

/**
 * Modal Alert System for AutiBloom
 * Converts Django messages to Bootstrap modal dialogs
 * Handles redirects after showing success messages
 */

document.addEventListener('DOMContentLoaded', function() {
    const messageData = document.getElementById('message-data');
    
    if (!messageData) return;

    try {
        const messages = JSON.parse(messageData.textContent);
        
        if (messages && messages.length > 0) {
            // Display first message in queue
            const message = messages[0];
            showAlert(message.type, message.message, message.redirect, message.redirect_url);
        }
    } catch (error) {
        console.error('Error parsing messages:', error);
    }
});

/**
 * Display alert modal with title and message
 * @param {string} type - Message type: 'success', 'error', 'warning', 'info'
 * @param {string} message - Message text to display
 * @param {boolean} shouldRedirect - Whether to redirect after showing modal
 * @param {string} redirectUrl - URL to redirect to after modal is dismissed
 */
function showAlert(type, message, shouldRedirect = false, redirectUrl = null) {
    const modalTitle = document.getElementById('alertModalLabel');
    const modalBody = document.getElementById('alertModalBody');
    const modalHeader = document.getElementById('alertModalHeader');
    const alertModal = new bootstrap.Modal(document.getElementById('alertModal'));
    
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
    
    // Handle redirect on modal close
    if (shouldRedirect && redirectUrl) {
        document.getElementById('alertModal').addEventListener('hidden.bs.modal', function() {
            window.location.href = redirectUrl;
        }, { once: true });
    }
    
    alertModal.show();
}

/**
 * Expose showAlert globally for manual triggers
 */
window.showAlert = showAlert;