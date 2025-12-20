'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ListChecks,
  Plus,
  Users,
  Calendar,
  ChevronRight,
  Filter,
  Star,
  Clock,
  Bookmark,
} from 'lucide-react';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';

// Note: Custom lists would typically be stored in a database table
// This is a placeholder implementation showing the UI structure
interface ContactList {
  id: string;
  name: string;
  description?: string;
  count: number;
  created_at: string;
  updated_at: string;
  is_favorite: boolean;
  filter: {
    contact_type?: string;
    category?: string;
    status?: string;
    territory?: string;
    tag?: string;
  };
}

// Example saved lists (in real implementation, this would come from API)
const savedLists: ContactList[] = [
  {
    id: '1',
    name: 'VIP Customers',
    description: 'High-value enterprise customers',
    count: 24,
    created_at: '2024-01-15',
    updated_at: '2024-01-20',
    is_favorite: true,
    filter: { category: 'enterprise', contact_type: 'customer' },
  },
  {
    id: '2',
    name: 'Hot Leads',
    description: 'Leads with high qualification score',
    count: 18,
    created_at: '2024-01-10',
    updated_at: '2024-01-19',
    is_favorite: true,
    filter: { contact_type: 'lead' },
  },
  {
    id: '3',
    name: 'Lagos Customers',
    description: 'All customers in Lagos territory',
    count: 156,
    created_at: '2024-01-05',
    updated_at: '2024-01-18',
    is_favorite: false,
    filter: { territory: 'Lagos', contact_type: 'customer' },
  },
  {
    id: '4',
    name: 'Churned - 2024',
    description: 'Customers who churned this year',
    count: 12,
    created_at: '2024-01-01',
    updated_at: '2024-01-17',
    is_favorite: false,
    filter: { contact_type: 'churned' },
  },
];

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export default function ListsPage() {
  const [filter, setFilter] = useState<'all' | 'favorites'>('all');

  const filteredLists = filter === 'favorites'
    ? savedLists.filter((l) => l.is_favorite)
    : savedLists;

  // Stats
  const totalLists = savedLists.length;
  const favoriteLists = savedLists.filter((l) => l.is_favorite).length;
  const totalContacts = savedLists.reduce((sum, l) => sum + l.count, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Custom Lists"
        subtitle="Saved contact segments and filters"
        icon={ListChecks}
        iconClassName="bg-indigo-500/10 border border-indigo-500/30"
        actions={
          <button
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-400 transition-colors"
            onClick={() => alert('Creating custom lists will be available soon. For now, you can filter contacts and bookmark the URL.')}
          >
            <Plus className="w-4 h-4" />
            New List
          </button>
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
              <p className="text-2xl font-bold text-white">{Math.round(totalContacts / totalLists)}</p>
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
            Favorites ({favoriteLists})
          </button>
        </div>
      </div>

      {/* Lists Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredLists.map((list) => {
          // Build filter URL
          const params = new URLSearchParams();
          if (list.filter.contact_type) params.set('type', list.filter.contact_type);
          if (list.filter.category) params.set('category', list.filter.category);
          if (list.filter.status) params.set('status', list.filter.status);
          if (list.filter.territory) params.set('territory', list.filter.territory);
          if (list.filter.tag) params.set('tag', list.filter.tag);
          const href = `/contacts?${params.toString()}`;

          return (
            <Link
              key={list.id}
              href={href}
              className="bg-slate-card rounded-xl border border-slate-border p-5 hover:border-indigo-500/50 transition-colors group"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-500/20 border border-indigo-500/30 rounded-lg">
                    <ListChecks className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-white font-semibold">{list.name}</h3>
                      {list.is_favorite && (
                        <Star className="w-4 h-4 text-amber-400" fill="currentColor" />
                      )}
                    </div>
                    {list.description && (
                      <p className="text-sm text-slate-muted">{list.description}</p>
                    )}
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-indigo-400 transition-colors" />
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1 text-slate-muted">
                  <Users className="w-4 h-4" />
                  <span><span className="text-white font-medium">{list.count}</span> contacts</span>
                </div>
                <div className="flex items-center gap-1 text-slate-muted">
                  <Calendar className="w-4 h-4" />
                  <span>Updated {formatDate(list.updated_at)}</span>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-border">
                <div className="flex flex-wrap gap-1">
                  {Object.entries(list.filter).map(([key, value]) => (
                    <span key={key} className="px-2 py-0.5 bg-slate-elevated rounded text-xs text-slate-muted">
                      {key}: {value}
                    </span>
                  ))}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {filteredLists.length === 0 && (
        <div className="bg-slate-card rounded-xl border border-slate-border p-8 text-center">
          <Bookmark className="w-12 h-12 text-slate-muted mx-auto mb-4" />
          <h3 className="text-white font-semibold mb-2">No lists found</h3>
          <p className="text-slate-muted text-sm mb-4">
            {filter === 'favorites'
              ? 'You haven\'t favorited any lists yet'
              : 'Create your first custom list to get started'}
          </p>
          <button
            className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-400 transition-colors inline-flex items-center gap-2"
            onClick={() => alert('Creating custom lists will be available soon')}
          >
            <Plus className="w-4 h-4" />
            Create List
          </button>
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
    </div>
  );
}
