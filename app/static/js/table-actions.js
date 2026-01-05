(function() {
    window.startInlineEdit = function(el) {
        const display = el.querySelector('.display-value');
        const editor = el.querySelector('.edit-input');
        if (!display || !editor) return;
        display.classList.add('hidden');
        editor.classList.remove('hidden');
        const input = editor.querySelector('input, select');
        if (input) input.focus();
    };

    window.cancelInlineEdit = function(el) {
        const display = el.querySelector('.display-value');
        const editor = el.querySelector('.edit-input');
        if (!display || !editor) return;
        display.classList.remove('hidden');
        editor.classList.add('hidden');
    };

    // Expose component factories as global functions for spread syntax usage
    window.bulkSelect = () => ({
        selectedIds: [],
        allSelected: false,

        toggleAll(checked, selector = '[data-bulk-id]') {
            this.allSelected = checked;
            const checkboxes = document.querySelectorAll(selector);
            this.selectedIds = checked
                ? Array.from(checkboxes).map(el => el.dataset.bulkId)
                : [];
        },

        toggleOne(id, checked) {
            if (checked) {
                if (!this.selectedIds.includes(id)) this.selectedIds.push(id);
            } else {
                this.selectedIds = this.selectedIds.filter(i => i !== id);
                this.allSelected = false;
            }
        },

        isSelected(id) {
            return this.selectedIds.includes(id);
        },

        clearSelection() {
            this.selectedIds = [];
            this.allSelected = false;
            document.querySelectorAll('[data-bulk-checkbox]').forEach(cb => cb.checked = false);
        },

        async deleteSelected(url, itemName) {
            const count = this.selectedIds.length;
            showModal(`
                <div class="text-center" data-modal="bulk-delete">
                    <div class="mx-auto w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
                        <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">Delete <span data-modal-count></span> <span data-modal-item></span>?</h3>
                    <p class="text-sm text-gray-500 mb-6">This action cannot be undone.</p>
                    <div class="flex gap-3 justify-center">
                        <button data-modal-close class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors">Cancel</button>
                        <button data-confirm-bulk-delete class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-xl hover:bg-red-500 transition-colors">Delete All</button>
                    </div>
                </div>
            `);
            const modalRoot = document.getElementById('modal-content');
            const modal = modalRoot?.querySelector('[data-modal="bulk-delete"]');
            const countEl = modal?.querySelector('[data-modal-count]');
            const itemEl = modal?.querySelector('[data-modal-item]');
            if (countEl) countEl.textContent = String(count);
            if (itemEl) itemEl.textContent = itemName || 'items';
            const cancelBtn = modal?.querySelector('[data-modal-close]');
            cancelBtn?.addEventListener('click', hideModal, { once: true });
            const confirmBtn = modal?.querySelector('[data-confirm-bulk-delete]');
            confirmBtn?.addEventListener('click', () => {
                hideModal();
                window.executeBulkDelete(url);
            }, { once: true });
        },

        async exportSelected(url) {
            const params = new URLSearchParams();
            this.selectedIds.forEach(id => params.append('ids', id));
            window.location.href = `${url}?${params.toString()}`;
        },

        async bulkAction(url, method, confirm, message) {
            if (confirm) {
                const confirmed = await window.showConfirmModal(message || 'Are you sure?');
                if (!confirmed) return;
            }
            await this.executeBulkAction(url, method);
        },

        async executeBulkAction(url, method = 'POST') {
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('[name="csrf_token"]')?.value || ''
                },
                body: JSON.stringify({ ids: this.selectedIds })
            });
            if (response.ok) {
                htmx.trigger(document.body, 'bulkActionComplete');
                this.clearSelection();
                showToast('Action completed', 'success');
            } else {
                showToast('Action failed', 'error');
            }
        }
    });

    window.columnPicker = (storageKey, columns) => ({
        columns,
        open: false,
        hidden: [],

        init() {
            const stored = window.localStorage.getItem(`columns:${storageKey}`);
            if (stored) {
                try {
                    this.hidden = JSON.parse(stored);
                } catch (error) {
                    this.hidden = [];
                }
            }
        },

        isRequired(key) {
            return Boolean(this.columns.find((col) => col.key === key)?.required);
        },

        isVisible(key) {
            if (this.isRequired(key)) return true;
            return !this.hidden.includes(key);
        },

        toggleColumn(key) {
            if (this.isRequired(key)) return;
            if (this.hidden.includes(key)) {
                this.hidden = this.hidden.filter((col) => col !== key);
            } else {
                this.hidden = [...this.hidden, key];
            }
            window.localStorage.setItem(`columns:${storageKey}`, JSON.stringify(this.hidden));
        },

        resetColumns() {
            this.hidden = [];
            window.localStorage.removeItem(`columns:${storageKey}`);
        }
    });

    document.addEventListener('alpine:init', () => {
        // Register with Alpine for backward compatibility
        Alpine.data('bulkSelect', window.bulkSelect);
        Alpine.data('columnPicker', window.columnPicker);
    });

    window.resetColumnPreferences = function() {
        const confirmed = window.confirm('Reset all table columns to defaults? This clears your saved column preferences.');
        if (!confirmed) return;
        const keys = [];
        for (let index = 0; index < window.localStorage.length; index += 1) {
            const key = window.localStorage.key(index);
            if (key && key.startsWith('columns:')) {
                keys.push(key);
            }
        }
        keys.forEach((key) => window.localStorage.removeItem(key));
        showToast('Column preferences reset', 'success');
    };

    window.executeBulkDelete = async function(url) {
        const root = document.querySelector('[x-data*="bulkSelect"]');
        if (!root || !window.Alpine) {
            showToast('Bulk actions are not available on this page.', 'error');
            return;
        }
        const component = Alpine.$data(root);
        if (!component) return;
        await component.executeBulkAction(url, 'DELETE');
        location.reload();
    };

    function isModalOpen() {
        const shortcutsModal = document.getElementById('keyboard-shortcuts-modal');
        if (shortcutsModal && shortcutsModal.getAttribute('aria-hidden') !== 'true') return true;
        return document.body.classList.contains('overflow-hidden');
    }

    document.addEventListener('keydown', (e) => {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
        if (e.target.isContentEditable) return;
        if (isModalOpen()) return;

        const rows = document.querySelectorAll('tbody tr[data-row-id]');
        if (!rows.length) return;

        let currentIndex = Array.from(rows).findIndex(r => r.classList.contains('ring-2'));

        switch (e.key) {
            case 'j':
                e.preventDefault();
                if (currentIndex < rows.length - 1) {
                    rows[currentIndex]?.classList.remove('ring-2', 'ring-primary-500');
                    rows[currentIndex + 1]?.classList.add('ring-2', 'ring-primary-500');
                    rows[currentIndex + 1]?.scrollIntoView({ block: 'nearest' });
                } else if (currentIndex === -1 && rows.length) {
                    rows[0]?.classList.add('ring-2', 'ring-primary-500');
                }
                break;

            case 'k':
                e.preventDefault();
                if (currentIndex > 0) {
                    rows[currentIndex]?.classList.remove('ring-2', 'ring-primary-500');
                    rows[currentIndex - 1]?.classList.add('ring-2', 'ring-primary-500');
                    rows[currentIndex - 1]?.scrollIntoView({ block: 'nearest' });
                }
                break;

            case 'Enter':
            case 'o':
                if (currentIndex >= 0) {
                    e.preventDefault();
                    const viewBtn = rows[currentIndex].querySelector('[data-action="view"], a[href*="/"]');
                    if (viewBtn) viewBtn.click();
                }
                break;

            case 'e':
                if (currentIndex >= 0) {
                    e.preventDefault();
                    const editBtn = rows[currentIndex].querySelector('[data-action="edit"], a[href*="/edit"]');
                    if (editBtn) editBtn.click();
                }
                break;

            case 'd':
                if (e.shiftKey && currentIndex >= 0) {
                    e.preventDefault();
                    const deleteBtn = rows[currentIndex].querySelector('[data-action="delete"], button[hx-delete]');
                    if (deleteBtn) deleteBtn.click();
                }
                break;

            case '/':
                e.preventDefault();
                const searchInput = document.querySelector('input[type="search"], input[name="q"]');
                if (searchInput) searchInput.focus();
                break;

            case 'Escape':
                rows.forEach(r => r.classList.remove('ring-2', 'ring-primary-500'));
                break;

            case 'x':
                if (currentIndex >= 0) {
                    e.preventDefault();
                    const checkbox = rows[currentIndex].querySelector('[data-bulk-checkbox]');
                    if (checkbox) {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                break;
        }
    });

    window.initInfiniteScroll = function(containerSelector, loadUrl, loadingId) {
        const container = document.querySelector(containerSelector);
        if (!container) return;

        let loading = false;
        let page = 1;
        let hasMore = true;

        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !loading && hasMore) {
                loading = true;
                page++;
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.classList.remove('hidden');

                fetch(`${loadUrl}?page=${page}`, {
                    headers: { 'HX-Request': 'true' }
                })
                    .then(res => res.text())
                    .then(html => {
                        if (html.trim()) {
                            container.insertAdjacentHTML('beforeend', html);
                            htmx.process(container);
                        } else {
                            hasMore = false;
                        }
                    })
                    .finally(() => {
                        loading = false;
                        if (loadingEl) loadingEl.classList.add('hidden');
                    });
            }
        }, { threshold: 0.1 });

        const sentinel = document.createElement('div');
        sentinel.id = 'infinite-scroll-sentinel';
        container.appendChild(sentinel);
        observer.observe(sentinel);
    };
})();
