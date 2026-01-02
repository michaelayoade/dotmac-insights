(function() {
    function toastManager() {
        return {
            toasts: [],
            nextId: 0,
            show(detail) {
                const id = this.nextId++;
                const toast = {
                    id,
                    message: detail.message,
                    type: detail.type || 'info',
                    entering: true,
                    leaving: false,
                    hidden: false
                };
                this.toasts.push(toast);

                setTimeout(() => { toast.entering = false; }, 300);
                setTimeout(() => this.dismiss(id), 5000);
            },
            dismiss(id) {
                const toast = this.toasts.find(t => t.id === id);
                if (toast && !toast.leaving) {
                    toast.leaving = true;
                    setTimeout(() => {
                        toast.hidden = true;
                        this.toasts = this.toasts.filter(t => t.id !== id);
                    }, 250);
                }
            }
        };
    }

    window.toastManager = toastManager;

    function globalSearch() {
        return {
            query: '',
            results: [],
            loading: false,
            open: false,
            focusedIndex: -1,

            get groupedResults() {
                const groups = {};
                for (const item of this.results) {
                    if (!groups[item.type]) {
                        groups[item.type] = { type: item.type, label: this.getLabel(item.type), items: [] };
                    }
                    groups[item.type].items.push(item);
                }
                return Object.values(groups);
            },

            get totalItems() {
                return this.results.length;
            },

            getLabel(type) {
                const labels = {
                    contact: 'Contacts',
                    customer: 'Customers',
                    ticket: 'Tickets',
                    invoice: 'Invoices',
                    employee: 'Employees',
                    project: 'Projects',
                    subscription: 'Subscriptions'
                };
                return labels[type] || type.charAt(0).toUpperCase() + type.slice(1) + 's';
            },

            getGlobalIndex(groupIndex, itemIndex) {
                let index = 0;
                for (let i = 0; i < groupIndex; i++) {
                    index += this.groupedResults[i].items.length;
                }
                return index + itemIndex;
            },

            getIconClass(type) {
                const classes = {
                    contact: 'bg-primary-50 text-primary-600',
                    customer: 'bg-blue-50 text-blue-600',
                    ticket: 'bg-amber-50 text-amber-600',
                    invoice: 'bg-emerald-50 text-emerald-600',
                    employee: 'bg-violet-50 text-violet-600',
                    project: 'bg-cyan-50 text-cyan-600',
                    subscription: 'bg-pink-50 text-pink-600'
                };
                return classes[type] || 'bg-gray-50 text-gray-600';
            },

            getIcon(type) {
                const icons = {
                    contact: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>',
                    customer: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>',
                    ticket: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"/></svg>',
                    invoice: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
                    employee: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2"/></svg>',
                    project: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>',
                    subscription: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'
                };
                return icons[type] || '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>';
            },

            getStatusClass(status) {
                if (!status) return '';
                const s = status.toLowerCase();
                if (['active', 'open', 'paid', 'approved'].includes(s)) {
                    return 'bg-emerald-100 text-emerald-700';
                }
                if (['pending', 'draft', 'unpaid'].includes(s)) {
                    return 'bg-amber-100 text-amber-700';
                }
                if (['closed', 'cancelled', 'inactive'].includes(s)) {
                    return 'bg-gray-100 text-gray-600';
                }
                return 'bg-gray-100 text-gray-600';
            },

            async search() {
                if (this.query.length < 2) {
                    this.results = [];
                    this.open = false;
                    return;
                }

                this.loading = true;
                this.open = true;

                try {
                    const response = await fetch(`/api/search?q=${encodeURIComponent(this.query)}`);
                    if (response.ok) {
                        const data = await response.json();
                        this.results = data.results || [];
                    } else {
                        this.results = [];
                    }
                } catch (e) {
                    this.results = [];
                } finally {
                    this.loading = false;
                    this.focusedIndex = -1;
                }
            },

            close() {
                this.open = false;
                this.focusedIndex = -1;
            },

            focusNext() {
                if (this.totalItems === 0) return;
                this.focusedIndex = (this.focusedIndex + 1) % this.totalItems;
            },

            focusPrev() {
                if (this.totalItems === 0) return;
                this.focusedIndex = this.focusedIndex <= 0 ? this.totalItems - 1 : this.focusedIndex - 1;
            },

            selectFocused() {
                if (this.focusedIndex >= 0 && this.focusedIndex < this.totalItems) {
                    const item = this.results[this.focusedIndex];
                    if (item && item.url) {
                        window.location.href = item.url;
                    }
                }
            },

            focusInput() {
                this.$el.querySelector('input')?.focus();
            }
        };
    }

    window.globalSearch = globalSearch;

    window.showToast = function(message, type = 'success') {
        window.dispatchEvent(new CustomEvent('show-toast', { detail: { message, type } }));
    };

    window.showModal = function(content) {
        const contentEl = document.getElementById('modal-content');
        if (contentEl) {
            contentEl.innerHTML = content;
            document.body.classList.add('overflow-hidden');
            window.dispatchEvent(new CustomEvent('open-modal'));
        }
    };

    window.hideModal = function() {
        document.body.classList.remove('overflow-hidden');
        window.dispatchEvent(new CustomEvent('close-modal'));
    };

    window.addEventListener('open-modal', function() {
        document.body.classList.add('overflow-hidden');
    });

    window.addEventListener('close-modal', function() {
        document.body.classList.remove('overflow-hidden');
    });

    document.addEventListener('htmx:afterRequest', function(evt) {
        const trigger = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (trigger) {
            try {
                const parsed = JSON.parse(trigger);
                if (parsed.showToast) {
                    window.dispatchEvent(new CustomEvent('show-toast', { detail: parsed.showToast }));
                }
                if (parsed.closeModal) {
                    window.dispatchEvent(new CustomEvent('close-modal'));
                }
            } catch (e) {
                // Ignore malformed HX-Trigger payloads.
            }
        }
    });

    document.addEventListener('htmx:responseError', function() {
        window.dispatchEvent(new CustomEvent('show-toast', {
            detail: { message: 'An error occurred. Please try again.', type: 'error' }
        }));
    });

    document.addEventListener('htmx:beforeSwap', function(evt) {
        if (evt.detail.xhr.status === 401) {
            const redirectUrl = evt.detail.xhr.getResponseHeader('HX-Redirect');
            window.location.href = redirectUrl || '/login';
            evt.detail.shouldSwap = false;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function(evt) {
        const toastMessage = evt.detail.xhr.getResponseHeader('HX-Toast');
        const toastType = evt.detail.xhr.getResponseHeader('HX-Toast-Type') || 'success';
        if (toastMessage) {
            showToast(decodeURIComponent(toastMessage), toastType);
        }

        if (evt.detail.target && evt.detail.target.id === 'main-content') {
            const contentTitle = document.querySelector('#main-content [data-testid="page-title"]');
            const titleText = contentTitle ? contentTitle.textContent.trim() : '';
            const fallbackTitle = evt.detail.target.dataset.pageTitle || '';
            const resolvedTitle = titleText || fallbackTitle;
            if (resolvedTitle) {
                const productName = document.body?.dataset?.productName || '';
                document.title = productName ? `${resolvedTitle} | ${productName}` : resolvedTitle;
            }
        }
    });

    document.body.addEventListener('htmx:confirm', function(evt) {
        if (evt.detail.question && evt.detail.elt.hasAttribute('hx-delete')) {
            evt.preventDefault();
            const itemName = evt.detail.elt.dataset.itemName || 'this item';
            const deleteId = evt.detail.elt.dataset.deleteId;
            if (!deleteId) {
                showToast('Delete action is missing an identifier.', 'error');
                return;
            }
            showModal(`
                <div class="text-center">
                    <div class="mx-auto w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
                        <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">Delete ${itemName}?</h3>
                    <p class="text-sm text-gray-500 mb-6">This action cannot be undone.</p>
                    <div class="flex gap-3 justify-center">
                        <button onclick="hideModal()" class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors">
                            Cancel
                        </button>
                        <button onclick="hideModal(); window.dispatchEvent(new CustomEvent('confirm-delete', { detail: { deleteId: '${deleteId}' } }))" class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-xl hover:bg-red-500 transition-colors">
                            Delete
                        </button>
                    </div>
                </div>
            `);

            const handleConfirm = function(event) {
                if (!event.detail || event.detail.deleteId !== deleteId) return;
                const deleteTarget = document.querySelector(`[data-delete-id='${deleteId}']`);
                if (!deleteTarget) {
                    showToast('Unable to find the item to delete. Please refresh and try again.', 'error');
                    return;
                }
                evt.detail.issueRequest();
            };

            window.addEventListener('confirm-delete', handleConfirm, { once: true });
        }
    });

    document.addEventListener('keydown', function(evt) {
        if (evt.key === 'Escape') {
            window.dispatchEvent(new CustomEvent('close-modal'));
        }

        if (evt.key === '?' && !['INPUT', 'TEXTAREA'].includes(evt.target.tagName)) {
            const shortcutsModal = document.getElementById('keyboard-shortcuts-modal');
            if (shortcutsModal) {
                shortcutsModal.classList.toggle('hidden');
            }
        }

        // Cmd/Ctrl+K to focus global search
        if ((evt.metaKey || evt.ctrlKey) && evt.key === 'k') {
            evt.preventDefault();
            const searchInput = document.querySelector('[data-testid="global-search-input"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
    });
})();
