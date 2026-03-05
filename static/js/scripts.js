// ===========================================
// TIRE MANAGEMENT SYSTEM - JAVASCRIPT
// Interactive Features & Utilities
// ===========================================

document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeModals();
    initializeForms();
    initializeFilters();
    initializeTireSelection();
    initializeAlerts();
});

// ===========================================
// SIDEBAR TOGGLE (Mobile)
// ===========================================

function initializeSidebar() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });

        // Close sidebar when clicking outside (mobile)
        document.addEventListener('click', function(event) {
            if (window.innerWidth <= 1024) {
                if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) {
                    sidebar.classList.remove('active');
                }
            }
        });
    }
}

// ===========================================
// MODAL SYSTEM
// ===========================================

function initializeModals() {
    // Open modals
    const modalTriggers = document.querySelectorAll('[data-modal-target]');
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-modal-target');
            openModal(modalId);
        });
    });

    // Close modals
    const closeButtons = document.querySelectorAll('.modal-close, [data-modal-close]');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            closeModal(modal.id);
        });
    });

    // Close on backdrop click
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => {
        backdrop.addEventListener('click', function() {
            const modalId = this.getAttribute('data-modal-id');
            closeModal(modalId);
        });
    });

    // Close on ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(modalId + '-backdrop');

    if (modal) {
        modal.classList.add('show');
        if (backdrop) {
            backdrop.classList.add('show');
        }
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(modalId + '-backdrop');

    if (modal) {
        modal.classList.remove('show');
        if (backdrop) {
            backdrop.classList.remove('show');
        }
        document.body.style.overflow = '';
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal.show').forEach(modal => {
        closeModal(modal.id);
    });
}

// ===========================================
// FORM VALIDATION & ENHANCEMENTS
// ===========================================

function initializeForms() {
    // Real-time validation
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input[required], select[required]');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });

            input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    validateField(this);
                }
            });
        });

        form.addEventListener('submit', function(e) {
            let isValid = true;
            inputs.forEach(input => {
                if (!validateField(input)) {
                    isValid = false;
                }
            });

            if (!isValid) {
                e.preventDefault();
                showAlert('Preencha todos os campos obrigatórios corretamente.', 'danger');
            }
        });
    });

    // Auto-calculate km based on laps
    const voltasInput = document.getElementById('voltas');
    const kmPorVolta = document.getElementById('km_por_volta_hidden');
    const quilometragemDisplay = document.getElementById('quilometragem_display');

    if (voltasInput && kmPorVolta && quilometragemDisplay) {
        voltasInput.addEventListener('input', function() {
            const voltas = parseFloat(this.value) || 0;
            const kmVolta = parseFloat(kmPorVolta.value) || 0;
            const totalKm = (voltas * kmVolta).toFixed(2);
            quilometragemDisplay.textContent = totalKm + ' km';
        });
    }

    // Calculate average depth
    const depthInputs = document.querySelectorAll('[data-depth-input]');
    const averageDisplay = document.getElementById('profundidade_media_display');

    if (depthInputs.length > 0 && averageDisplay) {
        depthInputs.forEach(input => {
            input.addEventListener('input', function() {
                let sum = 0;
                let count = 0;
                depthInputs.forEach(inp => {
                    const val = parseFloat(inp.value);
                    if (!isNaN(val)) {
                        sum += val;
                        count++;
                    }
                });
                const average = count > 0 ? (sum / count).toFixed(2) : '0.00';
                averageDisplay.textContent = average + ' mm';

                // Color code based on average
                if (parseFloat(average) > 2.0) {
                    averageDisplay.className = 'text-success';
                } else if (parseFloat(average) > 1.5) {
                    averageDisplay.className = 'text-warning';
                } else {
                    averageDisplay.className = 'text-danger';
                }
            });
        });
    }
}

function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';

    // Required check
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'Este campo é obrigatório';
    }

    // Type-specific validation
    if (value && field.type === 'email') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = 'Email inválido';
        }
    }

    if (value && field.type === 'number') {
        const min = field.getAttribute('min');
        const max = field.getAttribute('max');
        const numValue = parseFloat(value);

        if (min !== null && numValue < parseFloat(min)) {
            isValid = false;
            errorMessage = `Valor mínimo: ${min}`;
        }
        if (max !== null && numValue > parseFloat(max)) {
            isValid = false;
            errorMessage = `Valor máximo: ${max}`;
        }
    }

    // Update UI
    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        removeFieldError(field);
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        showFieldError(field, errorMessage);
    }

    return isValid;
}

function showFieldError(field, message) {
    removeFieldError(field);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.style.color = 'var(--status-critical)';
    errorDiv.style.fontSize = '0.875rem';
    errorDiv.style.marginTop = '0.25rem';
    errorDiv.textContent = message;
    field.parentNode.appendChild(errorDiv);
}

function removeFieldError(field) {
    const existingError = field.parentNode.querySelector('.field-error');
    if (existingError) {
        existingError.remove();
    }
}

// ===========================================
// FILTERS
// ===========================================

function initializeFilters() {
    const filterInputs = document.querySelectorAll('[data-filter]');

    filterInputs.forEach(input => {
        input.addEventListener('change', function() {
            applyFilters();
        });
    });
}

function applyFilters() {
    const filters = {};
    document.querySelectorAll('[data-filter]').forEach(input => {
        if (input.value) {
            filters[input.name] = input.value;
        }
    });

    // Build query string
    const params = new URLSearchParams(filters);
    window.location.search = params.toString();
}

function clearFilters() {
    document.querySelectorAll('[data-filter]').forEach(input => {
        input.value = '';
    });
    window.location.search = '';
}

// ===========================================
// TIRE SELECTION (for sets)
// ===========================================

function initializeTireSelection() {
    const tirePositions = document.querySelectorAll('.tire-position');

    tirePositions.forEach(position => {
        position.addEventListener('click', function() {
            const positionName = this.getAttribute('data-position');
            const modalId = 'selectTireModal-' + positionName;
            openModal(modalId);
        });
    });

    // Tire selection in modal
    const tireOptions = document.querySelectorAll('[data-tire-option]');
    tireOptions.forEach(option => {
        option.addEventListener('click', function() {
            const tireId = this.getAttribute('data-tire-id');
            const tireName = this.getAttribute('data-tire-name');
            const position = this.getAttribute('data-position');

            selectTire(position, tireId, tireName);
            closeAllModals();
        });
    });
}

function selectTire(position, tireId, tireName) {
    const positionElement = document.querySelector(`[data-position="${position}"]`);
    const hiddenInput = document.getElementById(`pneu_${position}`);

    if (positionElement) {
        positionElement.classList.add('selected');
        positionElement.querySelector('.tire-name').textContent = tireName;
    }

    if (hiddenInput) {
        hiddenInput.value = tireId;
    }

    checkSetCompletion();
}

function checkSetCompletion() {
    const positions = ['de', 'dd', 'te', 'td'];
    let allSelected = true;

    positions.forEach(pos => {
        const input = document.getElementById(`pneu_${pos}`);
        if (!input || !input.value) {
            allSelected = false;
        }
    });

    const submitButton = document.getElementById('submitSetButton');
    if (submitButton) {
        submitButton.disabled = !allSelected;
    }
}

// ===========================================
// ALERTS
// ===========================================

function initializeAlerts() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideOutUp 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Close button
    const closeButtons = document.querySelectorAll('.alert-close');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const alert = this.closest('.alert');
            alert.style.animation = 'slideOutUp 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        });
    });
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <i class="fas fa-${getAlertIcon(type)}"></i>
        <span>${message}</span>
        <button class="alert-close" style="background:none;border:none;font-size:1.2rem;cursor:pointer;margin-left:auto;">&times;</button>
    `;

    alertContainer.appendChild(alert);

    // Auto-dismiss
    setTimeout(() => {
        alert.style.animation = 'slideOutUp 0.3s ease';
        setTimeout(() => alert.remove(), 300);
    }, 5000);

    // Close button
    alert.querySelector('.alert-close').addEventListener('click', function() {
        alert.style.animation = 'slideOutUp 0.3s ease';
        setTimeout(() => alert.remove(), 300);
    });
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    container.style.position = 'fixed';
    container.style.top = '20px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.maxWidth = '400px';
    document.body.appendChild(container);
    return container;
}

function getAlertIcon(type) {
    const icons = {
        success: 'check-circle',
        warning: 'exclamation-triangle',
        danger: 'exclamation-circle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// ===========================================
// CONFIRMATION DIALOGS
// ===========================================

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Add to delete buttons
document.querySelectorAll('[data-confirm]').forEach(button => {
    button.addEventListener('click', function(e) {
        e.preventDefault();
        const message = this.getAttribute('data-confirm');
        const form = this.closest('form');

        if (confirm(message)) {
            if (form) {
                form.submit();
            }
        }
    });
});

// ===========================================
// UTILITY FUNCTIONS
// ===========================================

function formatNumber(num, decimals = 2) {
    return parseFloat(num).toFixed(decimals);
}

function formatKm(km) {
    return formatNumber(km, 2) + ' km';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
}

function getStatusBadge(status) {
    const badges = {
        'Novo': 'badge-ok',
        'Usado': 'badge-info',
        'Disponível': 'badge-ok',
        'Em uso': 'badge-warning',
        'Montado': 'badge-info',
        'Descartado': 'badge-critical'
    };
    return badges[status] || 'badge-neutral';
}

// ===========================================
// TABLE SORTING
// ===========================================

function initializeTableSort() {
    const sortableTables = document.querySelectorAll('[data-sortable]');

    sortableTables.forEach(table => {
        const headers = table.querySelectorAll('th[data-sort]');

        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                const column = this.getAttribute('data-sort');
                const order = this.getAttribute('data-order') || 'asc';
                sortTable(table, column, order);

                // Toggle order
                this.setAttribute('data-order', order === 'asc' ? 'desc' : 'asc');
            });
        });
    });
}

function sortTable(table, column, order) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort((a, b) => {
        const aValue = a.querySelector(`[data-value="${column}"]`)?.textContent || '';
        const bValue = b.querySelector(`[data-value="${column}"]`)?.textContent || '';

        if (order === 'asc') {
            return aValue.localeCompare(bValue, 'pt-BR', { numeric: true });
        } else {
            return bValue.localeCompare(aValue, 'pt-BR', { numeric: true });
        }
    });

    rows.forEach(row => tbody.appendChild(row));
}

// ===========================================
// LOADING SPINNER
// ===========================================

function showLoading() {
    const loader = document.createElement('div');
    loader.id = 'loadingSpinner';
    loader.innerHTML = `
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;">
            <div style="background:white;padding:2rem;border-radius:1rem;text-align:center;">
                <i class="fas fa-spinner fa-spin" style="font-size:3rem;color:var(--primary-color);"></i>
                <p style="margin-top:1rem;font-weight:600;">Carregando...</p>
            </div>
        </div>
    `;
    document.body.appendChild(loader);
}

function hideLoading() {
    const loader = document.getElementById('loadingSpinner');
    if (loader) {
        loader.remove();
    }
}

// ===========================================
// EXPORT TO PDF (placeholder)
// ===========================================

function exportToPDF(elementId) {
    showAlert('Função de exportação em desenvolvimento', 'info');
    // Backend já tem geração de PDF
}

// ===========================================
// KEYBOARD SHORTCUTS
// ===========================================

document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K = Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('[data-search]');
        if (searchInput) {
            searchInput.focus();
        }
    }

    // Ctrl/Cmd + N = New item (if on listing page)
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        const newButton = document.querySelector('[data-action="new"]');
        if (newButton) {
            newButton.click();
        }
    }
});

// ===========================================
// ANIMATIONS
// ===========================================

@keyframes slideOutUp {
    from {
        transform: translateY(0);
        opacity: 1;
    }
    to {
        transform: translateY(-20px);
        opacity: 0;
    }
}

// Initialize everything
console.log('🏎️ Tire Management System initialized');
