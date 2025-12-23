'use client';

import { useState } from 'react';
import { History, ChevronDown, Loader2 } from 'lucide-react';
import { useEntityHistory } from '@/hooks/useApi';
import { ChangeHistoryItem } from './ChangeHistoryItem';
import type { EntityType } from '@/lib/api/domains/projects';

interface ChangeHistoryProps {
  entityType: EntityType;
  entityId: number;
  title?: string;
  className?: string;
}

export function ChangeHistory({
  entityType,
  entityId,
  title = 'Change History',
  className = '',
}: ChangeHistoryProps) {
  const [limit, setLimit] = useState(20);
  const { data, isLoading, error } = useEntityHistory(entityType, entityId, { limit });

  const items = data?.data || [];
  const hasMore = data?.total && data.total > items.length;

  if (isLoading) {
    return (
      <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 ${className}`}>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 ${className}`}>
        <p className="text-center text-rose-400 py-4">Failed to load change history</p>
      </div>
    );
  }

  return (
    <div className={`bg-slate-800/50 border border-slate-700/50 rounded-lg ${className}`}>
      <div className="px-4 py-3 border-b border-slate-700/50 flex items-center gap-2">
        <History className="w-4 h-4 text-slate-400" />
        <h3 className="font-medium text-slate-200">{title}</h3>
        {data?.total !== undefined && (
          <span className="text-xs text-slate-500">({data.total} entries)</span>
        )}
      </div>

      <div className="p-4">
        {items.length === 0 ? (
          <div className="text-center py-8">
            <History className="w-10 h-10 mx-auto text-slate-600 mb-3" />
            <p className="text-slate-500">No history recorded yet</p>
          </div>
        ) : (
          <div className="space-y-0">
            {items.map((item) => (
              <ChangeHistoryItem key={item.id} item={item} />
            ))}
          </div>
        )}

        {hasMore && (
          <button
            onClick={() => setLimit(limit + 20)}
            className="w-full mt-4 py-2 flex items-center justify-center gap-1 text-sm text-amber-400 hover:text-amber-300 transition-colors"
          >
            <ChevronDown className="w-4 h-4" />
            Load more
          </button>
        )}
      </div>
    </div>
  );
}
