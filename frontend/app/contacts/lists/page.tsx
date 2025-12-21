'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ListChecks,
  Plus,
  Users,
  Calendar,
  ChevronRight,
  Star,
  Clock,
  Bookmark,
  Edit2,
  Trash2,
  X,
  Save,
  Loader2,
  Share2,
  Lock,
} from 'lucide-react';
import useSWR from 'swr';
import { apiFetch } from '@/hooks/useApi';
import { fetchApi } from '@/lib/api/core';
import { PageHeader } from '@/components/ui';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth-context';

interface ContactListFilters {
  contact_type?: string;
  category?: string;
  status?: string;
  qualification?: string;
  territory?: string;
  city?: string;
  state?: string;
  source?: string;
  is_organization?: boolean;
  has_outstanding?: boolean;
  tag?: string;
  quality_issue?: string;
}

interface ContactList {
  id: number;
  name: string;
  description?: string;
  owner_id: number;
  owner_name?: string;
  is_shared: boolean;
  is_favorite: boolean;
  filters?: ContactListFilters;
  color?: string;
  icon?: string;
  sort_order: number;
  contact_count: number;
  created_at: string;
  updated_at: string;
}

interface ContactListsResponse {
  items: ContactList[];
  total: number;
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function ListsPage() {
  const { hasScope } = useAuth();
  const canWrite = hasScope('contacts:write');
  const [filter, setFilter] = useState<'all' | 'favorites'>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingList, setEditingList] = useState<ContactList | null>(null);

  const { data, isLoading, error, mutate } = useSWR<ContactListsResponse>(
    `/contacts/lists?favorites_only=${filter === 'favorites'}`,
    apiFetch
  );

  const lists = data?.items || [];
  const totalLists = data?.total || 0;
  const favoriteLists = lists.filter((l) => l.is_favorite).length;
  const totalContacts = lists.reduce((sum, l) => sum + l.contact_count, 0);

  const handleToggleFavorite = async (listId: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await fetchApi(`/contacts/lists/${listId}/favorite`, { method: 'POST' });
      mutate();
    } catch (err) {
      console.error('Failed to toggle favorite:', err);
    }
  };

  const handleDelete = async (listId: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this list?')) return;
    try {
      await fetchApi(`/contacts/lists/${listId}`, { method: 'DELETE' });
      mutate();
    } catch (err) {
      console.error('Failed to delete list:', err);
    }
  };

  if (isLoading && !data) {
    return <LoadingState />;
  }

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load lists"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      <PageHeader
        title="Custom Lists"
        subtitle="Saved contact segments and filters"
        icon={ListChecks}
        iconClassName="bg-indigo-500/10 border border-indigo-500/30"
        actions={
          canWrite ? (
            <button
              className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-400 transition-colors"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="w-4 h-4" />
              New List
            </button>
          ) : null
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/20 rounded-lg">
              <ListChecks className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{totalLists}</p>
              <p className="text-xs text-slate-muted">Total Lists</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Star className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{favoriteLists}</p>
              <p className="text-xs text-slate-muted">Favorites</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Users className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{totalContacts}</p>
              <p className="text-xs text-slate-muted">Total Contacts</p>
            </div>
          </div>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Clock className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{totalLists > 0 ? Math.round(totalContacts / totalLists) : 0}</p>
              <p className="text-xs text-slate-muted">Avg per List</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilter('all')}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              filter === 'all'
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
            )}
          >
            All Lists ({totalLists})
          </button>
          <button
            onClick={() => setFilter('favorites')}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
              filter === 'favorites'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
            )}
          >
            <Star className="w-4 h-4" />
            Favorites
          </button>
        </div>
      </div>

      {/* Lists Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {lists.map((list) => {
          // Build filter URL
          const params = new URLSearchParams();
          if (list.filters?.contact_type) params.set('type', list.filters.contact_type);
          if (list.filters?.category) params.set('category', list.filters.category);
          if (list.filters?.status) params.set('status', list.filters.status);
          if (list.filters?.qualification) params.set('qualification', list.filters.qualification);
          if (list.filters?.territory) params.set('territory', list.filters.territory);
          if (list.filters?.tag) params.set('tag', list.filters.tag);
          if (list.filters?.quality_issue) params.set('quality_issue', list.filters.quality_issue);
          if (list.filters?.is_organization !== undefined) params.set('org', list.filters.is_organization ? '1' : '0');
          const href = `/contacts?${params.toString()}`;

          return (
            <Link
              key={list.id}
              href={href}
              className="bg-slate-card rounded-xl border border-slate-border p-5 hover:border-indigo-500/50 transition-colors group"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div
                    className="p-2 rounded-lg border"
                    style={{
                      backgroundColor: list.color ? `${list.color}20` : 'rgb(99 102 241 / 0.2)',
                      borderColor: list.color ? `${list.color}50` : 'rgb(99 102 241 / 0.3)',
                    }}
                  >
                    <ListChecks
                      className="w-5 h-5"
                      style={{ color: list.color || 'rgb(129 140 248)' }}
                    />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-white font-semibold">{list.name}</h3>
                      {list.is_favorite && (
                        <Star className="w-4 h-4 text-amber-400" fill="currentColor" />
                      )}
                      {list.is_shared ? (
                        <span title="Shared with team">
                          <Share2 className="w-3 h-3 text-slate-muted" />
                        </span>
                      ) : (
                        <span title="Private">
                          <Lock className="w-3 h-3 text-slate-muted" />
                        </span>
                      )}
                    </div>
                    {list.description && (
                      <p className="text-sm text-slate-muted">{list.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {canWrite && (
                    <>
                      <button
                        onClick={(e) => handleToggleFavorite(list.id, e)}
                        className="p-1.5 rounded hover:bg-slate-elevated transition-colors"
                        title={list.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        <Star
                          className={cn(
                            'w-4 h-4',
                            list.is_favorite ? 'text-amber-400' : 'text-slate-muted'
                          )}
                          fill={list.is_favorite ? 'currentColor' : 'none'}
                        />
                      </button>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setEditingList(list);
                        }}
                        className="p-1.5 rounded hover:bg-slate-elevated transition-colors"
                        title="Edit list"
                      >
                        <Edit2 className="w-4 h-4 text-slate-muted" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(list.id, e)}
                        className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
                        title="Delete list"
                      >
                        <Trash2 className="w-4 h-4 text-slate-muted hover:text-red-400" />
                      </button>
                    </>
                  )}
                  <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-indigo-400 transition-colors" />
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1 text-slate-muted">
                  <Users className="w-4 h-4" />
                  <span><span className="text-white font-medium">{list.contact_count}</span> contacts</span>
                </div>
                <div className="flex items-center gap-1 text-slate-muted">
                  <Calendar className="w-4 h-4" />
                  <span>Updated {formatDate(list.updated_at)}</span>
                </div>
              </div>

              {list.filters && Object.keys(list.filters).length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-border">
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(list.filters)
                      .filter(([, value]) => value !== null && value !== undefined)
                      .map(([key, value]) => (
                        <span key={key} className="px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                          {key}: {String(value)}
                        </span>
                      ))}
                  </div>
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {lists.length === 0 && !isLoading && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-8 text-center">
          <Bookmark className="w-12 h-12 text-slate-muted mx-auto mb-4" />
          <h3 className="text-white font-semibold mb-2">No lists found</h3>
          <p className="text-slate-muted text-sm mb-4">
            {filter === 'favorites'
              ? "You haven't favorited any lists yet"
              : 'Create your first custom list to get started'}
          </p>
          {canWrite && (
            <button
              className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-400 transition-colors inline-flex items-center gap-2"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="w-4 h-4" />
              Create List
            </button>
          )}
        </div>
      )}

      {/* Quick Links */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-4">
        <h3 className="text-white font-semibold mb-3">Quick Filters</h3>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/contacts?type=customer"
            className="px-3 py-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm hover:bg-emerald-500/30 transition-colors"
          >
            All Customers
          </Link>
          <Link
            href="/contacts?type=lead"
            className="px-3 py-2 bg-violet-500/20 text-violet-400 border border-violet-500/30 rounded-lg text-sm hover:bg-violet-500/30 transition-colors"
          >
            All Leads
          </Link>
          <Link
            href="/contacts?status=active"
            className="px-3 py-2 bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-lg text-sm hover:bg-cyan-500/30 transition-colors"
          >
            Active Contacts
          </Link>
          <Link
            href="/contacts?has_outstanding=true"
            className="px-3 py-2 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg text-sm hover:bg-amber-500/30 transition-colors"
          >
            With Outstanding
          </Link>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingList) && (
        <ListModal
          list={editingList}
          onClose={() => {
            setShowCreateModal(false);
            setEditingList(null);
          }}
          onSaved={() => {
            setShowCreateModal(false);
            setEditingList(null);
            mutate();
          }}
        />
      )}
    </div>
  );
}

function ListModal({
  list,
  onClose,
  onSaved,
}: {
  list: ContactList | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(list?.name || '');
  const [description, setDescription] = useState(list?.description || '');
  const [isShared, setIsShared] = useState(list?.is_shared ?? true);
  const [color, setColor] = useState(list?.color || '#6366F1');
  const [contactType, setContactType] = useState(list?.filters?.contact_type || '');
  const [category, setCategory] = useState(list?.filters?.category || '');
  const [status, setStatus] = useState(list?.filters?.status || '');
  const [territory, setTerritory] = useState(list?.filters?.territory || '');
  const [tag, setTag] = useState(list?.filters?.tag || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    setSaving(true);
    setError(null);

    const filters: ContactListFilters = {};
    if (contactType) filters.contact_type = contactType;
    if (category) filters.category = category;
    if (status) filters.status = status;
    if (territory) filters.territory = territory;
    if (tag) filters.tag = tag;

    const payload = {
      name: name.trim(),
      description: description.trim() || undefined,
      is_shared: isShared,
      color: color || undefined,
      filters: Object.keys(filters).length > 0 ? filters : undefined,
    };

    try {
      if (list) {
        await fetchApi(`/contacts/lists/${list.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
      } else {
        await fetchApi('/contacts/lists', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }
      onSaved();
    } catch (err) {
      setError('Failed to save list. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-lg w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-white">
            {list ? 'Edit List' : 'Create New List'}
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-700 transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., VIP Customers"
              className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Color
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="w-10 h-10 rounded border border-slate-600 cursor-pointer"
                />
                <span className="text-slate-400 text-sm">{color}</span>
              </div>
            </div>
            <div className="flex-1">
              <label className="flex items-center gap-3 cursor-pointer mt-6">
                <input
                  type="checkbox"
                  checked={isShared}
                  onChange={(e) => setIsShared(e.target.checked)}
                  className="w-5 h-5 rounded border-slate-600 bg-slate-900/50 text-indigo-500 focus:ring-indigo-500"
                />
                <span className="text-slate-300">Share with team</span>
              </label>
            </div>
          </div>

          <div className="border-t border-slate-700 pt-4">
            <h4 className="text-white font-medium mb-3">Filter Criteria</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Contact Type</label>
                <select
                  value={contactType}
                  onChange={(e) => setContactType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Any</option>
                  <option value="lead">Lead</option>
                  <option value="prospect">Prospect</option>
                  <option value="customer">Customer</option>
                  <option value="churned">Churned</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Any</option>
                  <option value="residential">Residential</option>
                  <option value="business">Business</option>
                  <option value="enterprise">Enterprise</option>
                  <option value="government">Government</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Any</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="suspended">Suspended</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Territory</label>
                <input
                  type="text"
                  value={territory}
                  onChange={(e) => setTerritory(e.target.value)}
                  placeholder="e.g., Lagos"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-slate-400 mb-1">Tag</label>
                <input
                  type="text"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  placeholder="e.g., vip"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-indigo-500 text-white hover:bg-indigo-400 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  {list ? 'Save Changes' : 'Create List'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
