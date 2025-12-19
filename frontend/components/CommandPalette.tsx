'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Search,
  X,
  ArrowRight,
  Clock,
  Zap,
  FileText,
  Users,
  Contact2,
  Ticket,
  FolderKanban,
  ClipboardList,
  UserCircle,
  Landmark,
  Receipt,
  Hash,
  Plus,
  LayoutDashboard,
  Briefcase,
  BookOpen,
  LifeBuoy,
  MessageSquare,
  Package,
  Truck,
  Wallet2,
  ShoppingCart,
  Bell,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MODULES } from '@/lib/config/modules';
import { getCardColors } from '@/lib/config/colors';
import { useMockGlobalSearch } from '@/hooks/useGlobalSearch';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';

// =============================================================================
// TYPES
// =============================================================================

interface QuickAction {
  id: string;
  label: string;
  description: string;
  href: string;
  icon: React.ElementType;
  category: 'create' | 'navigate';
}

interface RecentItem {
  id: string;
  title: string;
  href: string;
  type: string;
  timestamp: number;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const QUICK_ACTIONS: QuickAction[] = [
  { id: 'create-invoice', label: 'Create Invoice', description: 'New sales invoice', href: '/sales/invoices/new', icon: FileText, category: 'create' },
  { id: 'new-ticket', label: 'New Support Ticket', description: 'Create support ticket', href: '/support/tickets/new', icon: Ticket, category: 'create' },
  { id: 'add-contact', label: 'Add Contact', description: 'New contact', href: '/contacts/new', icon: Contact2, category: 'create' },
  { id: 'new-order', label: 'New Service Order', description: 'Field service order', href: '/field-service/orders/new', icon: ClipboardList, category: 'create' },
  { id: 'new-project', label: 'Create Project', description: 'New project', href: '/projects/new', icon: FolderKanban, category: 'create' },
  { id: 'new-po', label: 'New Purchase Order', description: 'Create PO', href: '/purchasing/orders/new', icon: ShoppingCart, category: 'create' },
];

const RECENT_STORAGE_KEY = 'dotmac_command_palette_recent';
const MAX_RECENT_ITEMS = 5;

// Icon mapping for entity types
const TYPE_ICONS: Record<string, React.ElementType> = {
  customer: Users,
  contact: Contact2,
  invoice: FileText,
  ticket: Ticket,
  project: FolderKanban,
  order: ClipboardList,
  employee: UserCircle,
  asset: Landmark,
  bill: Receipt,
};

// =============================================================================
// RECENT ITEMS STORAGE
// =============================================================================

function getRecentItems(): RecentItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const stored = localStorage.getItem(RECENT_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function addRecentItem(item: Omit<RecentItem, 'timestamp'>) {
  if (typeof window === 'undefined') return;
  try {
    const items = getRecentItems().filter((i) => i.id !== item.id);
    items.unshift({ ...item, timestamp: Date.now() });
    localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(items.slice(0, MAX_RECENT_ITEMS)));
  } catch {
    // Ignore storage errors
  }
}

// =============================================================================
// COMMAND PALETTE COMPONENT
// =============================================================================

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentItems, setRecentItems] = useState<RecentItem[]>([]);

  // Use mock search for now (will use real search when backend is ready)
  const { query, results: searchResults, search, clearSearch } = useMockGlobalSearch();

  // Load recent items on mount
  useEffect(() => {
    setRecentItems(getRecentItems());
  }, [isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 10);
      setSelectedIndex(0);
    } else {
      clearSearch();
    }
  }, [isOpen, clearSearch]);

  // Escape to close
  useKeyboardShortcut('Escape', onClose, { enabled: isOpen });

  // Build flat list of all items for keyboard navigation
  const allItems = useMemo(() => {
    const items: Array<{ id: string; type: 'recent' | 'action' | 'module' | 'result'; data: unknown; href: string }> = [];

    // If no search query, show recent + quick actions + modules
    if (!query || query.length < 2) {
      // Recent items
      recentItems.forEach((item) => {
        items.push({ id: `recent-${item.id}`, type: 'recent', data: item, href: item.href });
      });

      // Quick actions
      QUICK_ACTIONS.forEach((action) => {
        items.push({ id: `action-${action.id}`, type: 'action', data: action, href: action.href });
      });

      // Modules
      MODULES.forEach((mod) => {
        items.push({ id: `module-${mod.key}`, type: 'module', data: mod, href: mod.href });
      });
    } else {
      // Search results
      searchResults.forEach((result) => {
        items.push({ id: `result-${result.id}`, type: 'result', data: result, href: result.href });
      });

      // Filter quick actions by query
      QUICK_ACTIONS.filter(
        (a) =>
          a.label.toLowerCase().includes(query.toLowerCase()) ||
          a.description.toLowerCase().includes(query.toLowerCase())
      ).forEach((action) => {
        items.push({ id: `action-${action.id}`, type: 'action', data: action, href: action.href });
      });
    }

    return items;
  }, [query, searchResults, recentItems]);

  // Arrow key navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, allItems.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && allItems[selectedIndex]) {
        e.preventDefault();
        const item = allItems[selectedIndex];
        handleSelect(item.href, item.data);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, allItems]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const selected = listRef.current.querySelector('[data-selected="true"]');
    if (selected) {
      selected.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  const handleSelect = (href: string, data: unknown) => {
    // Add to recent items
    if (data && typeof data === 'object' && 'title' in data) {
      const item = data as { id: string; title: string; type?: string };
      addRecentItem({
        id: String(item.id),
        title: item.title,
        href,
        type: item.type || 'page',
      });
    } else if (data && typeof data === 'object' && 'name' in data) {
      const mod = data as { key: string; name: string };
      addRecentItem({
        id: mod.key,
        title: mod.name,
        href,
        type: 'module',
      });
    } else if (data && typeof data === 'object' && 'label' in data) {
      const action = data as { id: string; label: string };
      addRecentItem({
        id: action.id,
        title: action.label,
        href,
        type: 'action',
      });
    }

    onClose();
    router.push(href);
  };

  if (!isOpen) return null;

  const showRecent = recentItems.length > 0 && (!query || query.length < 2);
  const showQuickActions = !query || query.length < 2;
  const showModules = !query || query.length < 2;
  const showSearchResults = query && query.length >= 2 && searchResults.length > 0;

  let itemIndex = -1;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative min-h-full flex items-start justify-center pt-[15vh] px-4 pb-8">
        <div className="relative w-full max-w-2xl bg-slate-card border border-slate-border rounded-2xl shadow-2xl overflow-hidden">
          {/* Search input */}
          <div className="flex items-center gap-3 p-4 border-b border-slate-border">
            <Search className="w-5 h-5 text-slate-muted flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => search(e.target.value)}
              placeholder="Search or type a command..."
              className="flex-1 bg-transparent text-white text-lg placeholder:text-slate-muted focus:outline-none"
            />
            <div className="flex items-center gap-2 flex-shrink-0">
              <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-1 bg-slate-elevated border border-slate-border rounded text-xs text-slate-muted">
                esc
              </kbd>
              <button
                onClick={onClose}
                aria-label="Close command palette"
                className="p-1 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
              >
                <X className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[60vh] overflow-y-auto p-2">
            {/* Recent items */}
            {showRecent && (
              <div className="mb-4">
                <div className="px-3 py-2 text-xs font-semibold text-slate-muted uppercase tracking-wide flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5" />
                  Recent
                </div>
                {recentItems.map((item) => {
                  itemIndex++;
                  const isSelected = selectedIndex === itemIndex;
                  return (
                    <button
                      key={item.id}
                      data-selected={isSelected}
                      onClick={() => handleSelect(item.href, item)}
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                        isSelected ? 'bg-teal-500/20 text-teal-300' : 'text-white hover:bg-slate-elevated'
                      )}
                    >
                      <Clock className="w-4 h-4 text-slate-muted" />
                      <span className="flex-1 truncate">{item.title}</span>
                      <ArrowRight className={cn('w-4 h-4', isSelected ? 'text-teal-400' : 'text-slate-muted')} />
                    </button>
                  );
                })}
              </div>
            )}

            {/* Quick actions */}
            {showQuickActions && (
              <div className="mb-4">
                <div className="px-3 py-2 text-xs font-semibold text-slate-muted uppercase tracking-wide flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5" />
                  Quick Actions
                </div>
                {QUICK_ACTIONS.map((action) => {
                  itemIndex++;
                  const isSelected = selectedIndex === itemIndex;
                  const Icon = action.icon;
                  return (
                    <button
                      key={action.id}
                      data-selected={isSelected}
                      onClick={() => handleSelect(action.href, action)}
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                        isSelected ? 'bg-teal-500/20 text-teal-300' : 'text-white hover:bg-slate-elevated'
                      )}
                    >
                      <div className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center',
                        isSelected ? 'bg-teal-500/30' : 'bg-slate-elevated'
                      )}>
                        <Icon className={cn('w-4 h-4', isSelected ? 'text-teal-400' : 'text-slate-muted')} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{action.label}</p>
                        <p className="text-xs text-slate-muted truncate">{action.description}</p>
                      </div>
                      <Plus className={cn('w-4 h-4', isSelected ? 'text-teal-400' : 'text-slate-muted')} />
                    </button>
                  );
                })}
              </div>
            )}

            {/* Modules navigation */}
            {showModules && (
              <div className="mb-4">
                <div className="px-3 py-2 text-xs font-semibold text-slate-muted uppercase tracking-wide flex items-center gap-2">
                  <LayoutDashboard className="w-3.5 h-3.5" />
                  Go to Module
                </div>
                <div className="grid grid-cols-2 gap-1">
                  {MODULES.map((mod) => {
                    itemIndex++;
                    const isSelected = selectedIndex === itemIndex;
                    const Icon = mod.icon;
                    const colors = getCardColors(mod.accentColor);
                    return (
                      <button
                        key={mod.key}
                        data-selected={isSelected}
                        onClick={() => handleSelect(mod.href, mod)}
                        className={cn(
                          'flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors',
                          isSelected ? 'bg-teal-500/20 text-teal-300' : 'text-white hover:bg-slate-elevated'
                        )}
                      >
                        <Icon className={cn('w-4 h-4', isSelected ? 'text-teal-400' : colors.text)} />
                        <span className="truncate text-sm">{mod.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Search results */}
            {showSearchResults && (
              <div>
                <div className="px-3 py-2 text-xs font-semibold text-slate-muted uppercase tracking-wide flex items-center gap-2">
                  <Search className="w-3.5 h-3.5" />
                  Results
                </div>
                {searchResults.map((result) => {
                  itemIndex++;
                  const isSelected = selectedIndex === itemIndex;
                  const Icon = TYPE_ICONS[result.type] || Hash;
                  return (
                    <button
                      key={result.id}
                      data-selected={isSelected}
                      onClick={() => handleSelect(result.href, result)}
                      className={cn(
                        'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                        isSelected ? 'bg-teal-500/20 text-teal-300' : 'text-white hover:bg-slate-elevated'
                      )}
                    >
                      <div className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center',
                        isSelected ? 'bg-teal-500/30' : 'bg-slate-elevated'
                      )}>
                        <Icon className={cn('w-4 h-4', isSelected ? 'text-teal-400' : 'text-slate-muted')} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{result.title}</p>
                        {result.subtitle && (
                          <p className="text-xs text-slate-muted truncate">{result.subtitle}</p>
                        )}
                      </div>
                      <ArrowRight className={cn('w-4 h-4', isSelected ? 'text-teal-400' : 'text-slate-muted')} />
                    </button>
                  );
                })}
              </div>
            )}

            {/* No results */}
            {query && query.length >= 2 && searchResults.length === 0 && (
              <div className="px-3 py-8 text-center">
                <Search className="w-10 h-10 text-slate-muted mx-auto mb-3 opacity-50" />
                <p className="text-slate-muted">No results found for &ldquo;{query}&rdquo;</p>
                <p className="text-sm text-slate-muted mt-1">Try a different search term</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-border bg-slate-elevated/50 text-xs text-slate-muted">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-slate-border rounded">↑</kbd>
                <kbd className="px-1.5 py-0.5 bg-slate-border rounded">↓</kbd>
                <span className="ml-1">Navigate</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-slate-border rounded">↵</kbd>
                <span className="ml-1">Select</span>
              </span>
            </div>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-slate-border rounded">esc</kbd>
              <span className="ml-1">Close</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
