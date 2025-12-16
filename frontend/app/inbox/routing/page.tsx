'use client';

import { useState } from 'react';
import {
  GitBranch,
  Plus,
  Trash2,
  Edit,
  ToggleLeft,
  ToggleRight,
  ArrowRight,
  MessageCircle,
  Users,
  Tag,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useInboxRoutingRules,
  useInboxRoutingRuleMutations,
} from '@/hooks/useInbox';
import type { InboxRoutingRule, RoutingCondition } from '@/lib/inbox.types';
import {
  PageHeader,
  EmptyState,
  ErrorState,
  StatGrid,
  Button,
} from '@/components/ui';
import { StatCard } from '@/components/StatCard';

function RoutingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="bg-slate-card border border-slate-border rounded-xl p-5 animate-pulse">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 bg-slate-elevated rounded" />
              <div>
                <div className="h-5 w-32 bg-slate-elevated rounded mb-2" />
                <div className="h-4 w-48 bg-slate-elevated rounded" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-20 bg-slate-elevated rounded" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="h-6 w-24 bg-slate-elevated rounded" />
            <div className="h-6 w-6 bg-slate-elevated rounded" />
            <div className="h-6 w-24 bg-slate-elevated rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}


const CONDITION_ICONS: Record<string, React.ElementType> = {
  channel: MessageCircle,
  keyword: Tag,
  tag: Tag,
  priority: AlertCircle,
  contact_company: Users,
};

const ACTION_ICONS: Record<string, React.ElementType> = {
  assign_team: Users,
  assign_agent: Users,
  create_ticket: GitBranch,
  add_tag: Tag,
  set_priority: AlertCircle,
};

export default function RoutingPage() {
  const [isCreating, setIsCreating] = useState(false);

  const {
    data: rulesData,
    error: rulesError,
    isLoading: rulesLoading,
    mutate: refreshRules,
  } = useInboxRoutingRules();

  const mutations = useInboxRoutingRuleMutations();

  const rules = rulesData?.data || [];
  const activeCount = rules.filter((r) => r.is_active).length;
  const totalMatches = rules.reduce((sum, r) => sum + (r.match_count || 0), 0);

  const handleToggleRule = async (rule: InboxRoutingRule) => {
    try {
      await mutations.toggleRule(rule.id);
    } catch (error) {
      console.error('Failed to toggle rule:', error);
    }
  };

  const handleDeleteRule = async (rule: InboxRoutingRule) => {
    if (!confirm(`Are you sure you want to delete "${rule.name}"?`)) return;
    try {
      await mutations.deleteRule(rule.id);
    } catch (error) {
      console.error('Failed to delete rule:', error);
    }
  };

  const renderConditions = (conditions: RoutingCondition[]) => {
    return conditions.map((cond, idx) => {
      const Icon = CONDITION_ICONS[cond.type] || Tag;
      return (
        <span key={idx} className="flex items-center gap-2">
          {idx > 0 && <span className="text-xs text-slate-muted">AND</span>}
          <span className="px-2 py-1 rounded bg-slate-elevated text-xs text-slate-200 flex items-center gap-1">
            <Icon className="w-3 h-3" />
            {cond.type}: {cond.operator} "{cond.value}"
          </span>
        </span>
      );
    });
  };

  const getActionLabel = (actionType: string, actionValue: string | undefined | null) => {
    const labels: Record<string, string> = {
      assign_team: `Assign to team`,
      assign_agent: `Assign to agent`,
      create_ticket: `Create ticket`,
      add_tag: `Add tag`,
      set_priority: `Set priority`,
    };
    const label = labels[actionType] || actionType;
    return actionValue ? `${label}: ${actionValue}` : label;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Routing Rules"
        subtitle="Auto-assign conversations based on conditions"
        icon={GitBranch}
        iconClassName="bg-violet-500/10 border border-violet-500/30"
        actions={
          <Button onClick={() => setIsCreating(true)} icon={Plus}>
            New Rule
          </Button>
        }
      />

      {/* Stats */}
      <StatGrid columns={4}>
        <StatCard
          title="Total Rules"
          value={rules.length}
          loading={rulesLoading}
          icon={GitBranch}
        />
        <StatCard
          title="Active"
          value={activeCount}
          loading={rulesLoading}
          icon={GitBranch}
          variant="success"
        />
        <StatCard
          title="Total Matches"
          value={totalMatches}
          loading={rulesLoading}
        />
        <StatCard
          title="Auto-Routed"
          value={`${rules.length > 0 ? Math.round((activeCount / rules.length) * 100) : 0}%`}
          loading={rulesLoading}
          variant="warning"
        />
      </StatGrid>

      {/* Rules list */}
      {rulesLoading ? (
        <RoutingSkeleton />
      ) : rulesError ? (
        <ErrorState message="Failed to load routing rules" onRetry={() => refreshRules()} />
      ) : rules.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No routing rules"
          description="Create rules to automatically route conversations"
          action={{ label: 'Create First Rule', icon: Plus, onClick: () => setIsCreating(true) }}
        />
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => {
            const ActionIcon = ACTION_ICONS[rule.action_type] || GitBranch;
            return (
              <div
                key={rule.id}
                className={cn(
                  'bg-slate-card border rounded-xl p-5 transition-colors',
                  rule.is_active ? 'border-slate-border' : 'border-slate-border/50 opacity-60'
                )}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleToggleRule(rule)}
                      className={cn('transition-colors', rule.is_active ? 'text-emerald-400' : 'text-slate-muted')}
                      aria-label={rule.is_active ? 'Disable rule' : 'Enable rule'}
                    >
                      {rule.is_active ? <ToggleRight className="w-6 h-6" /> : <ToggleLeft className="w-6 h-6" />}
                    </button>
                    <div>
                      <h3 className="text-white font-semibold">{rule.name}</h3>
                      {rule.description && <p className="text-sm text-slate-muted">{rule.description}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-muted">{rule.match_count || 0} matches</span>
                    <button
                      className="p-2 text-slate-muted hover:text-white hover:bg-slate-elevated rounded-lg transition-colors"
                      aria-label="Edit rule"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteRule(rule)}
                      className="p-2 text-slate-muted hover:text-rose-400 hover:bg-slate-elevated rounded-lg transition-colors"
                      aria-label="Delete rule"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-4 flex-wrap">
                  {/* Conditions */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-slate-muted uppercase">If</span>
                    {renderConditions(rule.conditions || [])}
                  </div>

                  <ArrowRight className="w-4 h-4 text-slate-muted" />

                  {/* Action */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-muted uppercase">Then</span>
                    <span className="px-2 py-1 rounded bg-blue-500/20 text-xs text-blue-400 flex items-center gap-1">
                      <ActionIcon className="w-3 h-3" />
                      {getActionLabel(rule.action_type, rule.action_value)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Help section */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="text-white font-semibold mb-3">How Routing Works</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold">1</div>
            <p className="text-white font-medium">Message Arrives</p>
            <p className="text-slate-muted">When a new conversation starts, the system evaluates all active rules in priority order.</p>
          </div>
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center text-violet-400 font-bold">2</div>
            <p className="text-white font-medium">Conditions Match</p>
            <p className="text-slate-muted">Rules check channel, keywords, tags, priority, and contact attributes.</p>
          </div>
          <div className="space-y-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">3</div>
            <p className="text-white font-medium">Action Executes</p>
            <p className="text-slate-muted">First matching rule triggers: assign to team/agent, add tags, or create tickets.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
