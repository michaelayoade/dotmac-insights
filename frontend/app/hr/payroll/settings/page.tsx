'use client';

import { useState, useMemo } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrSalaryComponents,
  useHrSalaryStructures,
  useDeductionRules,
  usePayrollRegions,
  useDeductionRuleMutations,
  usePayrollRegionMutations,
  useTaxBands,
  useTaxBandMutations,
} from '@/hooks/useApi';
import { hrApi } from '@/lib/api/domains/hr';
import { useSWRConfig } from 'swr';
import { cn, formatCurrency } from '@/lib/utils';
import { formatStatusLabel, type StatusTone } from '@/lib/status-pill';
import { Button, StatusPill, LoadingState, BackButton, Modal } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import {
  Settings,
  DollarSign,
  FileSpreadsheet,
  Calculator,
  Globe,
  Plus,
  Edit,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Percent,
  Layers,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type {
  HrSalaryComponent,
  HrSalaryStructure,
  DeductionRule,
  PayrollRegion,
  DeductionRulePayload,
  PayrollRegionPayload,
  TaxBand,
  TaxBandPayload,
  DeductionRuleType,
  CalculationMethod,
} from '@/lib/api';

function extractList<T>(response: any): { items: T[]; total: number } {
  const items = response?.data || response?.items || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

type TabId = 'components' | 'structures' | 'rules' | 'regions';

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'components', label: 'Salary Components', icon: DollarSign },
  { id: 'structures', label: 'Salary Structures', icon: FileSpreadsheet },
  { id: 'rules', label: 'Deduction Rules', icon: Calculator },
  { id: 'regions', label: 'Payroll Regions', icon: Globe },
];

const RULE_TYPES: DeductionRuleType[] = ['TAX', 'PENSION', 'NHF', 'NHIS', 'NSITF', 'ITF', 'OTHER'];
const CALC_METHODS: CalculationMethod[] = ['FLAT', 'PERCENTAGE', 'PROGRESSIVE'];

function RuleTypeLabel({ type }: { type: string }) {
  const colors: Record<string, string> = {
    TAX: 'text-red-400 bg-red-400/10',
    PENSION: 'text-blue-400 bg-blue-400/10',
    NHF: 'text-violet-400 bg-violet-400/10',
    NHIS: 'text-green-400 bg-green-400/10',
    NSITF: 'text-orange-400 bg-orange-400/10',
    ITF: 'text-teal-400 bg-teal-400/10',
    OTHER: 'text-slate-muted bg-slate-elevated',
  };
  return (
    <span className={cn('px-2 py-0.5 rounded text-xs font-medium', colors[type] || colors.OTHER)}>
      {type}
    </span>
  );
}

function CalcMethodLabel({ method }: { method: string }) {
  const icons: Record<string, LucideIcon> = {
    FLAT: DollarSign,
    PERCENTAGE: Percent,
    PROGRESSIVE: Layers,
  };
  const Icon = icons[method] || DollarSign;
  return (
    <span className="flex items-center gap-1 text-sm text-slate-muted">
      <Icon className="w-3.5 h-3.5" />
      {method}
    </span>
  );
}

export default function PayrollSettingsPage() {
  const { isLoading: authLoading, missingScope, hasScope } = useRequireScope('hr:read');
  const canWrite = hasScope('hr:write');

  const [activeTab, setActiveTab] = useState<TabId>('components');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Data
  const { data: componentsData, isLoading: componentsLoading } = useHrSalaryComponents();
  const { data: structuresData, isLoading: structuresLoading } = useHrSalaryStructures();
  const { data: rulesData, isLoading: rulesLoading, mutate: mutateRules } = useDeductionRules();
  const { data: regionsData, isLoading: regionsLoading, mutate: mutateRegions } = usePayrollRegions();

  const { items: components } = extractList<HrSalaryComponent>(componentsData);
  const { items: structures } = extractList<HrSalaryStructure>(structuresData);
  const { items: rules } = extractList<DeductionRule>(rulesData);
  const { items: regions } = extractList<PayrollRegion>(regionsData);

  // Mutations
  const ruleMutations = useDeductionRuleMutations();
  const regionMutations = usePayrollRegionMutations();

  // Modals
  const [showRuleModal, setShowRuleModal] = useState(false);
  const [editingRule, setEditingRule] = useState<DeductionRule | null>(null);
  const [ruleForm, setRuleForm] = useState<Partial<DeductionRulePayload>>({
    name: '',
    rule_type: 'TAX',
    calculation_method: 'FLAT',
    is_active: true,
  });

  const [showRegionModal, setShowRegionModal] = useState(false);
  const [editingRegion, setEditingRegion] = useState<PayrollRegion | null>(null);
  const [regionForm, setRegionForm] = useState<Partial<PayrollRegionPayload>>({
    country_code: 'NG',
    currency: 'NGN',
  });

  const [actionLoading, setActionLoading] = useState(false);

  // Rule handlers
  const handleOpenRuleModal = (rule?: DeductionRule) => {
    if (rule) {
      setEditingRule(rule);
      setRuleForm({
        name: rule.name,
        rule_type: rule.rule_type,
        calculation_method: rule.calculation_method,
        flat_amount: rule.flat_amount,
        percentage: rule.percentage,
        cap: rule.cap,
        floor: rule.floor,
        employer_contribution_percent: rule.employer_contribution_percent,
        employee_contribution_percent: rule.employee_contribution_percent,
        is_active: rule.is_active,
      });
    } else {
      setEditingRule(null);
      setRuleForm({
        name: '',
        rule_type: 'TAX',
        calculation_method: 'FLAT',
        is_active: true,
      });
    }
    setShowRuleModal(true);
  };

  const handleSaveRule = async () => {
    if (!ruleForm.name?.trim()) {
      setError('Rule name is required');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      if (editingRule) {
        await ruleMutations.update(editingRule.id, ruleForm);
        setSuccess('Deduction rule updated successfully');
      } else {
        await ruleMutations.create(ruleForm as DeductionRulePayload);
        setSuccess('Deduction rule created successfully');
      }
      setShowRuleModal(false);
      mutateRules();
    } catch (err: any) {
      setError(err?.message || 'Failed to save deduction rule');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteRule = async (id: number) => {
    if (!confirm('Are you sure you want to delete this deduction rule?')) return;
    setActionLoading(true);
    setError(null);
    try {
      await ruleMutations.delete(id);
      setSuccess('Deduction rule deleted');
      mutateRules();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete rule');
    } finally {
      setActionLoading(false);
    }
  };

  // Region handlers
  const handleOpenRegionModal = (region?: PayrollRegion) => {
    if (region) {
      setEditingRegion(region);
      setRegionForm({
        country_code: region.country_code,
        currency: region.currency,
      });
    } else {
      setEditingRegion(null);
      setRegionForm({ country_code: 'NG', currency: 'NGN' });
    }
    setShowRegionModal(true);
  };

  const handleSaveRegion = async () => {
    if (!regionForm.country_code?.trim() || !regionForm.currency?.trim()) {
      setError('Country and currency are required');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      if (editingRegion) {
        await regionMutations.update(editingRegion.id, regionForm);
        setSuccess('Payroll region updated successfully');
      } else {
        await regionMutations.create(regionForm as PayrollRegionPayload);
        setSuccess('Payroll region created successfully');
      }
      setShowRegionModal(false);
      mutateRegions();
    } catch (err: any) {
      setError(err?.message || 'Failed to save payroll region');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteRegion = async (id: number) => {
    if (!confirm('Are you sure you want to delete this payroll region?')) return;
    setActionLoading(true);
    setError(null);
    try {
      await regionMutations.delete(id);
      setSuccess('Payroll region deleted');
      mutateRegions();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete region');
    } finally {
      setActionLoading(false);
    }
  };

  // Permission guard
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the hr:read permission to view payroll settings."
        backHref="/hr/payroll"
        backLabel="Back to Payroll"
      />
    );
  }

  const componentColumns = [
    { header: 'Component', accessor: (row: HrSalaryComponent) => row.salary_component },
    { header: 'Abbr', accessor: (row: HrSalaryComponent) => row.abbr || '-' },
    {
      header: 'Type',
      accessor: (row: HrSalaryComponent) => (
        <span className={cn(
          'px-2 py-0.5 rounded text-xs font-medium',
          row.type === 'Earning' ? 'text-green-400 bg-green-400/10' : 'text-red-400 bg-red-400/10'
        )}>
          {row.type === 'Earning' ? <TrendingUp className="w-3 h-3 inline mr-1" /> : <TrendingDown className="w-3 h-3 inline mr-1" />}
          {row.type}
        </span>
      ),
    },
    { header: 'Company', accessor: (row: HrSalaryComponent) => row.company || '-' },
  ];

  const structureColumns = [
    { header: 'Name', accessor: (row: HrSalaryStructure) => row.name },
    { header: 'Company', accessor: (row: HrSalaryStructure) => row.company || '-' },
    { header: 'Currency', accessor: (row: HrSalaryStructure) => row.currency || 'NGN' },
    {
      header: 'Status',
      accessor: (row: HrSalaryStructure) => (
        <StatusPill
          label={row.is_active ? 'Active' : 'Inactive'}
          tone={row.is_active ? 'success' : 'muted'}
        />
      ),
    },
    { header: 'Earnings', accessor: (row: HrSalaryStructure) => row.earnings?.length || 0 },
    { header: 'Deductions', accessor: (row: HrSalaryStructure) => row.deductions?.length || 0 },
  ];

  const ruleColumns = [
    { header: 'Name', accessor: (row: DeductionRule) => row.name },
    { header: 'Type', accessor: (row: DeductionRule) => <RuleTypeLabel type={row.rule_type} /> },
    { header: 'Method', accessor: (row: DeductionRule) => <CalcMethodLabel method={row.calculation_method} /> },
    {
      header: 'Rate/Amount',
      accessor: (row: DeductionRule) => {
        if (row.calculation_method === 'FLAT') {
          return formatCurrency(row.flat_amount || 0, 'NGN');
        } else if (row.calculation_method === 'PERCENTAGE') {
          return `${row.percentage || 0}%`;
        }
        return 'Progressive';
      },
    },
    {
      header: 'Status',
      accessor: (row: DeductionRule) => (
        <StatusPill label={row.is_active ? 'Active' : 'Inactive'} tone={row.is_active ? 'success' : 'muted'} />
      ),
    },
    ...(canWrite
      ? [
          {
            header: 'Actions',
            accessor: (row: DeductionRule) => (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => handleOpenRuleModal(row)}>
                  <Edit className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDeleteRule(row.id)} className="text-red-400 hover:text-red-300">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  const regionColumns = [
    { header: 'Country', accessor: (row: PayrollRegion) => row.country_code },
    { header: 'Currency', accessor: (row: PayrollRegion) => row.currency },
    { header: 'Linked Rules', accessor: (row: PayrollRegion) => row.deduction_rules?.length || 0 },
    ...(canWrite
      ? [
          {
            header: 'Actions',
            accessor: (row: PayrollRegion) => (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => handleOpenRegionModal(row)}>
                  <Edit className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDeleteRegion(row.id)} className="text-red-400 hover:text-red-300">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BackButton href="/hr/payroll" label="Payroll" />
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Payroll</p>
            <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
              <Settings className="w-5 h-5 text-violet-400" />
              Payroll Settings
            </h1>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="ml-auto">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-border overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
              activeTab === tab.id
                ? 'text-teal-electric border-teal-electric'
                : 'text-slate-muted border-transparent hover:text-foreground'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'components' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-slate-muted text-sm">
              Manage salary components (earnings and deductions) used in salary structures.
            </p>
          </div>
          {componentsLoading ? (
            <LoadingState message="Loading components..." />
          ) : components.length === 0 ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
              <DollarSign className="w-12 h-12 text-slate-muted mx-auto mb-3" />
              <h3 className="text-foreground font-semibold mb-1">No Salary Components</h3>
              <p className="text-slate-muted text-sm">Salary components will appear here.</p>
            </div>
          ) : (
            <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <DataTable columns={componentColumns} data={components} />
            </div>
          )}
        </div>
      )}

      {activeTab === 'structures' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-slate-muted text-sm">
              Salary structures combine components into templates that can be assigned to employees.
            </p>
          </div>
          {structuresLoading ? (
            <LoadingState message="Loading structures..." />
          ) : structures.length === 0 ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
              <FileSpreadsheet className="w-12 h-12 text-slate-muted mx-auto mb-3" />
              <h3 className="text-foreground font-semibold mb-1">No Salary Structures</h3>
              <p className="text-slate-muted text-sm">Salary structures will appear here.</p>
            </div>
          ) : (
            <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <DataTable columns={structureColumns} data={structures} />
            </div>
          )}
        </div>
      )}

      {activeTab === 'rules' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-slate-muted text-sm">
              Configure tax and statutory deduction rules (PAYE, Pension, NHF, NHIS, etc.).
            </p>
            {canWrite && (
              <Button onClick={() => handleOpenRuleModal()} className="flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Add Rule
              </Button>
            )}
          </div>
          {rulesLoading ? (
            <LoadingState message="Loading deduction rules..." />
          ) : rules.length === 0 ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
              <Calculator className="w-12 h-12 text-slate-muted mx-auto mb-3" />
              <h3 className="text-foreground font-semibold mb-1">No Deduction Rules</h3>
              <p className="text-slate-muted text-sm mb-4">Configure tax and statutory deduction rules.</p>
              {canWrite && (
                <Button onClick={() => handleOpenRuleModal()} className="flex items-center gap-2 mx-auto">
                  <Plus className="w-4 h-4" />
                  Add Rule
                </Button>
              )}
            </div>
          ) : (
            <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <DataTable columns={ruleColumns} data={rules} />
            </div>
          )}
        </div>
      )}

      {activeTab === 'regions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-slate-muted text-sm">
              Configure payroll regions with country-specific tax and deduction rules.
            </p>
            {canWrite && (
              <Button onClick={() => handleOpenRegionModal()} className="flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Add Region
              </Button>
            )}
          </div>
          {regionsLoading ? (
            <LoadingState message="Loading payroll regions..." />
          ) : regions.length === 0 ? (
            <div className="bg-slate-card border border-slate-border rounded-xl p-8 text-center">
              <Globe className="w-12 h-12 text-slate-muted mx-auto mb-3" />
              <h3 className="text-foreground font-semibold mb-1">No Payroll Regions</h3>
              <p className="text-slate-muted text-sm mb-4">Configure payroll regions for different countries.</p>
              {canWrite && (
                <Button onClick={() => handleOpenRegionModal()} className="flex items-center gap-2 mx-auto">
                  <Plus className="w-4 h-4" />
                  Add Region
                </Button>
              )}
            </div>
          ) : (
            <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
              <DataTable columns={regionColumns} data={regions} />
            </div>
          )}
        </div>
      )}

      {/* Deduction Rule Modal */}
      <Modal isOpen={showRuleModal} onClose={() => setShowRuleModal(false)} title={editingRule ? 'Edit Deduction Rule' : 'Add Deduction Rule'}>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm text-slate-muted">Rule Name *</label>
            <input
              type="text"
              value={ruleForm.name || ''}
              onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="e.g., PAYE Tax"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Rule Type</label>
              <select
                value={ruleForm.rule_type || 'TAX'}
                onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value as DeductionRuleType })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                {RULE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Calculation Method</label>
              <select
                value={ruleForm.calculation_method || 'FLAT'}
                onChange={(e) => setRuleForm({ ...ruleForm, calculation_method: e.target.value as CalculationMethod })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              >
                {CALC_METHODS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>
          {ruleForm.calculation_method === 'FLAT' && (
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Flat Amount</label>
              <input
                type="number"
                value={ruleForm.flat_amount || ''}
                onChange={(e) => setRuleForm({ ...ruleForm, flat_amount: parseFloat(e.target.value) || undefined })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="0.00"
              />
            </div>
          )}
          {ruleForm.calculation_method === 'PERCENTAGE' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Percentage (%)</label>
                <input
                  type="number"
                  step="0.01"
                  value={ruleForm.percentage || ''}
                  onChange={(e) => setRuleForm({ ...ruleForm, percentage: parseFloat(e.target.value) || undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-slate-muted">Cap (Max)</label>
                <input
                  type="number"
                  value={ruleForm.cap || ''}
                  onChange={(e) => setRuleForm({ ...ruleForm, cap: parseFloat(e.target.value) || undefined })}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                  placeholder="No cap"
                />
              </div>
            </div>
          )}
          {ruleForm.calculation_method === 'PROGRESSIVE' && (
            <div className="bg-slate-elevated border border-slate-border rounded-lg p-3">
              <p className="text-sm text-slate-muted">
                Progressive tax bands can be configured after creating the rule.
              </p>
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={ruleForm.is_active ?? true}
              onChange={(e) => setRuleForm({ ...ruleForm, is_active: e.target.checked })}
              className="rounded border-slate-border"
            />
            <label htmlFor="is_active" className="text-sm text-foreground">Active</label>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowRuleModal(false)}>Cancel</Button>
            <Button onClick={handleSaveRule} disabled={actionLoading} loading={actionLoading}>
              {editingRule ? 'Update' : 'Create'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Payroll Region Modal */}
      <Modal isOpen={showRegionModal} onClose={() => setShowRegionModal(false)} title={editingRegion ? 'Edit Payroll Region' : 'Add Payroll Region'}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Country Code *</label>
              <input
                type="text"
                value={regionForm.country_code || ''}
                onChange={(e) => setRegionForm({ ...regionForm, country_code: e.target.value.toUpperCase() })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="NG"
                maxLength={2}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-slate-muted">Currency *</label>
              <input
                type="text"
                value={regionForm.currency || ''}
                onChange={(e) => setRegionForm({ ...regionForm, currency: e.target.value.toUpperCase() })}
                className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
                placeholder="NGN"
                maxLength={3}
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="secondary" onClick={() => setShowRegionModal(false)}>Cancel</Button>
            <Button onClick={handleSaveRegion} disabled={actionLoading} loading={actionLoading}>
              {editingRegion ? 'Update' : 'Create'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
