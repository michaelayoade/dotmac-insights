'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  DollarSign,
  Calendar,
  Building2,
  GripVertical,
  TrendingUp,
} from 'lucide-react';
import { useKanbanView, usePipelineView, useOpportunityMutations, usePipelineStages } from '@/hooks/useApi';
import { formatDate } from '@/lib/date';
import { formatCurrency } from '@/lib/formatters';
import type { KanbanColumn } from '@/lib/api';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { LoadingState } from '@/components/ui';

const stageColors: Record<string, string> = {
  slate: 'border-slate-500 bg-slate-500/10',
  blue: 'border-blue-500 bg-blue-500/10',
  amber: 'border-amber-500 bg-amber-500/10',
  orange: 'border-orange-500 bg-orange-500/10',
  emerald: 'border-emerald-500 bg-emerald-500/10',
  red: 'border-red-500 bg-red-500/10',
};

export default function PipelinePage() {
  const { isLoading: authLoading, missingScope } = useRequireScope('crm:read');
  const [ownerId, setOwnerId] = useState<number | undefined>();
  const { data: kanban, isLoading } = useKanbanView(ownerId);
  const { data: pipelineView } = usePipelineView();
  const { moveStage } = useOpportunityMutations();

  const [draggingOpp, setDraggingOpp] = useState<number | null>(null);
  const [dragOverStage, setDragOverStage] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, oppId: number) => {
    setDraggingOpp(oppId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, stageId: number) => {
    e.preventDefault();
    setDragOverStage(stageId);
  };

  const handleDragLeave = () => {
    setDragOverStage(null);
  };

  const handleDrop = async (e: React.DragEvent, stageId: number) => {
    e.preventDefault();
    setDragOverStage(null);

    if (draggingOpp) {
      try {
        await moveStage(draggingOpp, stageId);
      } catch (error) {
        console.error('Failed to move opportunity:', error);
      }
    }
    setDraggingOpp(null);
  };

  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the crm:read permission to view the pipeline."
        backHref="/crm"
        backLabel="Back to CRM"
      />
    );
  }

  if (isLoading) {
    return <LoadingState message="Loading pipeline..." />;
  }

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Sales Pipeline</h1>
          <p className="text-sm text-slate-400 mt-1">
            Drag opportunities between stages to update their progress
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/crm/pipeline/opportunities"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-foreground rounded-lg transition-colors"
          >
            List View
          </Link>
          <Link
            href="/crm/pipeline/opportunities/new"
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-foreground rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Deal
          </Link>
        </div>
      </div>

      {/* Summary Bar */}
      {pipelineView && (
        <div className="flex items-center gap-6 px-4 py-3 bg-slate-800/30 border border-slate-700/50 rounded-xl">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <span className="text-sm text-slate-400">Total Pipeline:</span>
            <span className="text-foreground font-medium">
              {formatCurrency(pipelineView.total_value ?? 0)}
            </span>
          </div>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Weighted:</span>
            <span className="text-cyan-400 font-medium">
              {formatCurrency(pipelineView.weighted_value ?? 0)}
            </span>
          </div>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Deals:</span>
            <span className="text-foreground font-medium">{kanban?.total_opportunities || 0}</span>
          </div>
        </div>
      )}

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto">
        <div className="flex gap-4 min-h-[calc(100vh-320px)] pb-4">
          {kanban?.columns?.map((column: KanbanColumn) => (
            <div
              key={column.stage_id}
              className={`flex-shrink-0 w-80 flex flex-col rounded-xl border-t-2 ${
                stageColors[column.color || 'slate'] || stageColors.slate
              } ${dragOverStage === column.stage_id ? 'ring-2 ring-cyan-500/50' : ''}`}
              onDragOver={(e) => handleDragOver(e, column.stage_id)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, column.stage_id)}
            >
              {/* Column Header */}
              <div className="p-4 bg-slate-800/50 rounded-t-xl">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-foreground">{column.stage_name}</h3>
                  <span className="text-xs text-slate-400 bg-slate-700/50 px-2 py-0.5 rounded-full">
                    {column.count}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">{formatCurrency(column.value ?? 0)}</span>
                  <span className="text-slate-500">{column.probability}%</span>
                </div>
              </div>

              {/* Column Body */}
              <div className="flex-1 p-2 space-y-2 overflow-y-auto bg-slate-800/20">
                {column.opportunities.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-32 text-slate-500 text-sm">
                    <p>No deals</p>
                    <p className="text-xs">Drag deals here</p>
                  </div>
                ) : (
                  column.opportunities.map((opp: KanbanColumn['opportunities'][number]) => (
                    <div
                      key={opp.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, opp.id)}
                      className={`bg-slate-800/80 border border-slate-700/50 rounded-lg p-3 cursor-grab active:cursor-grabbing hover:border-slate-600 transition-colors ${
                        draggingOpp === opp.id ? 'opacity-50' : ''
                      }`}
                    >
                      <Link href={`/crm/pipeline/opportunities/${opp.id}`}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium text-foreground text-sm truncate">{opp.name}</h4>
                            {opp.customer_name && (
                              <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1 truncate">
                                <Building2 className="w-3 h-3 flex-shrink-0" />
                                {opp.customer_name}
                              </p>
                            )}
                          </div>
                          <GripVertical className="w-4 h-4 text-slate-500 flex-shrink-0" />
                        </div>

                        <div className="flex items-center justify-between mt-3">
                          <div className="flex items-center gap-1 text-cyan-400 text-sm font-medium">
                            <DollarSign className="w-3 h-3" />
                            {formatCurrency(opp.deal_value ?? 0)}
                          </div>
                          <div className={`text-xs px-1.5 py-0.5 rounded ${
                            opp.probability >= 70 ? 'bg-emerald-500/20 text-emerald-400' :
                            opp.probability >= 40 ? 'bg-amber-500/20 text-amber-400' :
                            'bg-slate-500/20 text-slate-400'
                          }`}>
                            {opp.probability}%
                          </div>
                        </div>

                        {opp.expected_close_date && (
                          <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
                            <Calendar className="w-3 h-3" />
                            {formatDate(opp.expected_close_date, 'MMM d')}
                          </div>
                        )}
                      </Link>
                    </div>
                  ))
                )}
              </div>

              {/* Column Footer - Add Deal */}
              <Link
                href={`/crm/pipeline/opportunities/new?stage_id=${column.stage_id}`}
                className="flex items-center justify-center gap-2 p-3 bg-slate-800/30 hover:bg-slate-800/50 text-slate-400 hover:text-foreground transition-colors rounded-b-xl"
              >
                <Plus className="w-4 h-4" />
                <span className="text-sm">Add Deal</span>
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
