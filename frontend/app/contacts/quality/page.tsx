'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  ShieldCheck,
  Mail,
  Phone,
  MapPin,
  Building2,
  Users,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronRight,
  BarChart3,
  TrendingUp,
  Eye,
  Tag,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import useSWR from 'swr';
import { apiFetch } from '@/hooks/useApi';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { PageHeader } from '@/components/ui';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/lib/design-tokens';

interface QualityIssueData {
  field: string;
  label: string;
  count: number;
  percentage: number;
  severity: 'high' | 'medium' | 'low';
}

interface QualityAnalytics {
  total_contacts: number;
  quality_score: number;
  complete_contacts: number;
  completeness_rate: number;
  issues: QualityIssueData[];
}

// Icon mapping for issues
const ISSUE_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  phone: Phone,
  address: MapPin,
  company: Building2,
  territory: MapPin,
  category: Users,
  tags: Tag,
  invalid_email: XCircle,
};

// Map issue field names to quality_issue filter values
const ISSUE_FILTER_MAP: Record<string, string> = {
  email: 'missing_email',
  phone: 'missing_phone',
  address: 'missing_address',
  company: 'missing_company',
  invalid_email: 'invalid_email',
};

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: CHART_COLORS.tooltip.bg,
    border: `1px solid ${CHART_COLORS.tooltip.border}`,
    borderRadius: '8px',
  },
  labelStyle: { color: CHART_COLORS.tooltip.text },
};

export default function QualityPage() {
  const [viewIssue, setViewIssue] = useState<string | null>(null);

  // Fetch quality analytics from backend
  const { data: analytics, isLoading: analyticsLoading, error: analyticsError, mutate: mutateAnalytics } = useSWR<QualityAnalytics>(
    '/contacts/analytics/quality',
    apiFetch
  );

  // Use analytics data
  const totalContacts = analytics?.total_contacts || 0;
  const qualityScore = analytics?.quality_score || 100;
  const completeContacts = analytics?.complete_contacts || 0;
  const completenessRate = analytics?.completeness_rate || 100;
  const qualityIssues = useMemo(() => analytics?.issues || [], [analytics?.issues]);

  // Chart data
  const issuesByType = useMemo(() => {
    return qualityIssues.map((issue) => ({
      name: issue.label,
      value: issue.count,
      color: issue.severity === 'high'
        ? '#ef4444'
        : issue.severity === 'medium'
          ? '#f59e0b'
          : '#6b7280',
    }));
  }, [qualityIssues]);

  const severityData = useMemo(() => {
    return [
      { name: 'High', value: qualityIssues.filter(i => i.severity === 'high').reduce((s, i) => s + i.count, 0), color: '#ef4444' },
      { name: 'Medium', value: qualityIssues.filter(i => i.severity === 'medium').reduce((s, i) => s + i.count, 0), color: '#f59e0b' },
      { name: 'Low', value: qualityIssues.filter(i => i.severity === 'low').reduce((s, i) => s + i.count, 0), color: '#6b7280' },
    ].filter(s => s.value > 0);
  }, [qualityIssues]);

  if (analyticsLoading && !analytics) {
    return <LoadingState />;
  }

  // View specific issue contacts - redirect to filtered contacts list
  if (viewIssue) {
    const issue = qualityIssues.find((i) => i.field === viewIssue);
    const Icon = ISSUE_ICONS[viewIssue] || AlertTriangle;
    const filterParam = ISSUE_FILTER_MAP[viewIssue];

    if (issue) {
      return (
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setViewIssue(null)}
              className="text-slate-muted hover:text-white transition-colors"
            >
              &larr; Back to Quality Report
            </button>
          </div>

          <PageHeader
            title={issue.label}
            subtitle={`${issue.count} contacts with this issue (${issue.percentage}%)`}
            icon={Icon}
            iconClassName={cn(
              'border',
              issue.severity === 'high'
                ? 'bg-red-500/10 border-red-500/30'
                : issue.severity === 'medium'
                  ? 'bg-amber-500/10 border-amber-500/30'
                  : 'bg-slate-500/10 border-slate-500/30'
            )}
          />

          <div className="bg-slate-card rounded-xl border border-slate-border p-6 text-center">
            <Icon className={cn(
              'w-12 h-12 mx-auto mb-4',
              issue.severity === 'high'
                ? 'text-red-400'
                : issue.severity === 'medium'
                  ? 'text-amber-400'
                  : 'text-slate-400'
            )} />
            <h3 className="text-white font-semibold mb-2">{issue.count} Contacts Affected</h3>
            <p className="text-slate-muted text-sm mb-4">
              Click below to view and fix contacts with this data quality issue.
            </p>
            <Link
              href={filterParam ? `/contacts?quality_issue=${filterParam}` : '/contacts'}
              className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 text-white rounded-lg hover:bg-violet-400 transition-colors"
            >
              <Eye className="w-4 h-4" />
              View Affected Contacts
            </Link>
          </div>
        </div>
      );
    }
  }

  return (
    <div className="space-y-6">
      {analyticsError && (
        <ErrorDisplay
          message="Failed to analyze data quality"
          error={analyticsError as Error}
          onRetry={() => {
            mutateAnalytics();
          }}
        />
      )}

      <PageHeader
        title="Data Quality"
        subtitle="Analyze and improve contact data completeness"
        icon={ShieldCheck}
        iconClassName="bg-violet-500/10 border border-violet-500/30"
      />

      {/* Quality Score */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-card rounded-xl border border-slate-border p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-muted text-sm">Quality Score</span>
            <ShieldCheck className={cn(
              'w-5 h-5',
              qualityScore >= 80 ? 'text-emerald-400' : qualityScore >= 60 ? 'text-amber-400' : 'text-red-400'
            )} />
          </div>
          <p className={cn(
            'text-4xl font-bold',
            qualityScore >= 80 ? 'text-emerald-400' : qualityScore >= 60 ? 'text-amber-400' : 'text-red-400'
          )}>
            {qualityScore}%
          </p>
          <p className="text-xs text-slate-muted mt-1">
            {qualityScore >= 80 ? 'Good' : qualityScore >= 60 ? 'Needs Improvement' : 'Poor'}
          </p>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-muted text-sm">Total Contacts</span>
            <Users className="w-5 h-5 text-cyan-400" />
          </div>
          <p className="text-4xl font-bold text-white">{totalContacts}</p>
          <p className="text-xs text-slate-muted mt-1">Analyzed</p>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-muted text-sm">Complete Records</span>
            <CheckCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-4xl font-bold text-emerald-400">{completeContacts}</p>
          <p className="text-xs text-slate-muted mt-1">{completenessRate}% completeness</p>
        </div>
        <div className="bg-slate-card rounded-xl border border-slate-border p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-muted text-sm">Issues Found</span>
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <p className="text-4xl font-bold text-amber-400">{qualityIssues.length}</p>
          <p className="text-xs text-slate-muted mt-1">Types of issues</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Issues by Severity */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Issues by Severity</h3>
          </div>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={severityData}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {severityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend
                  formatter={(value) => <span className="text-slate-muted text-xs">{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: '10px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center">
              <div className="text-center">
                <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-2" />
                <p className="text-slate-muted text-sm">No issues found!</p>
              </div>
            </div>
          )}
        </div>

        {/* Issues Distribution */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-violet-400" />
            <h3 className="text-white font-semibold">Issue Distribution</h3>
          </div>
          {issuesByType.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={issuesByType.slice(0, 6)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis type="number" stroke={CHART_COLORS.axis} fontSize={12} />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke={CHART_COLORS.axis}
                  fontSize={10}
                  width={100}
                  tickFormatter={(value) => value.length > 15 ? value.substring(0, 15) + '...' : value}
                />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="value" fill={CHART_COLORS.palette[0]} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-muted text-sm">
              No data to display
            </div>
          )}
        </div>
      </div>

      {/* Quality Issues List */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-5">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h3 className="text-white font-semibold">Quality Issues</h3>
        </div>

        {qualityIssues.length > 0 ? (
          <div className="space-y-3">
            {qualityIssues.map((issue) => {
              const Icon = ISSUE_ICONS[issue.field] || AlertTriangle;

              return (
                <button
                  key={issue.field}
                  onClick={() => setViewIssue(issue.field)}
                  className="w-full flex items-center justify-between p-4 rounded-xl bg-slate-elevated hover:bg-slate-elevated/80 transition-colors text-left"
                >
                  <div className="flex items-center gap-4">
                    <div className={cn(
                      'p-2 rounded-lg',
                      issue.severity === 'high'
                        ? 'bg-red-500/20'
                        : issue.severity === 'medium'
                          ? 'bg-amber-500/20'
                          : 'bg-slate-500/20'
                    )}>
                      <Icon className={cn(
                        'w-5 h-5',
                        issue.severity === 'high'
                          ? 'text-red-400'
                          : issue.severity === 'medium'
                            ? 'text-amber-400'
                            : 'text-slate-400'
                      )} />
                    </div>
                    <div>
                      <p className="text-white font-medium">{issue.label}</p>
                      <p className="text-sm text-slate-muted">
                        {issue.count} contacts ({issue.percentage}%)
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={cn(
                      'px-2 py-1 rounded text-xs',
                      issue.severity === 'high'
                        ? 'bg-red-500/20 text-red-400'
                        : issue.severity === 'medium'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-slate-500/20 text-slate-400'
                    )}>
                      {issue.severity}
                    </span>
                    <ChevronRight className="w-5 h-5 text-slate-muted" />
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="py-8 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <h3 className="text-white font-semibold mb-2">Excellent Data Quality!</h3>
            <p className="text-slate-muted text-sm">
              No quality issues were found in your contact data.
            </p>
          </div>
        )}
      </div>

      {/* Recommendations */}
      <div className="bg-slate-card rounded-xl border border-slate-border p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <h3 className="text-white font-semibold">Recommendations</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-slate-elevated rounded-lg">
            <h4 className="text-white font-medium mb-2">Required Fields</h4>
            <p className="text-sm text-slate-muted mb-3">
              Ensure all contacts have email and phone for effective communication.
            </p>
            <Link
              href="/contacts?missing=email"
              className="text-violet-400 text-sm hover:text-violet-300 transition-colors"
            >
              View contacts missing email &rarr;
            </Link>
          </div>
          <div className="p-4 bg-slate-elevated rounded-lg">
            <h4 className="text-white font-medium mb-2">Segmentation</h4>
            <p className="text-sm text-slate-muted mb-3">
              Assign territories and categories for better reporting and targeting.
            </p>
            <Link
              href="/contacts/territories"
              className="text-violet-400 text-sm hover:text-violet-300 transition-colors"
            >
              Manage territories &rarr;
            </Link>
          </div>
          <div className="p-4 bg-slate-elevated rounded-lg">
            <h4 className="text-white font-medium mb-2">Duplicates</h4>
            <p className="text-sm text-slate-muted mb-3">
              Regularly check for and merge duplicate records to maintain clean data.
            </p>
            <Link
              href="/contacts/duplicates"
              className="text-violet-400 text-sm hover:text-violet-300 transition-colors"
            >
              Find duplicates &rarr;
            </Link>
          </div>
          <div className="p-4 bg-slate-elevated rounded-lg">
            <h4 className="text-white font-medium mb-2">Enrichment</h4>
            <p className="text-sm text-slate-muted mb-3">
              Add company details and social profiles to build complete customer profiles.
            </p>
            <Link
              href="/contacts/all"
              className="text-violet-400 text-sm hover:text-violet-300 transition-colors"
            >
              Browse all contacts &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
