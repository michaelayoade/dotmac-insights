'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Save,
  Target,
  Building2,
  DollarSign,
  Calendar,
  User,
  Percent,
  FileText,
} from 'lucide-react';
import { useOpportunityMutations, usePipelineStages, useCustomers, useLeads } from '@/hooks/useApi';
import type { PipelineStage, Lead } from '@/lib/api';

interface OpportunityFormData {
  name: string;
  description: string;
  customer_id: number | null;
  lead_id: number | null;
  stage_id: number | null;
  deal_value: number;
  probability: number;
  currency: string;
  expected_close_date: string;
  source: string;
  campaign: string;
}

const initialFormData: OpportunityFormData = {
  name: '',
  description: '',
  customer_id: null,
  lead_id: null,
  stage_id: null,
  deal_value: 0,
  probability: 0,
  currency: 'NGN',
  expected_close_date: '',
  source: '',
  campaign: '',
};

export default function NewOpportunityPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formData, setFormData] = useState<OpportunityFormData>(initialFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customerSearch, setCustomerSearch] = useState('');
  const [leadSearch, setLeadSearch] = useState('');

  const { createOpportunity } = useOpportunityMutations();
  const { data: stages } = usePipelineStages();
  const { data: customers } = useCustomers({ search: customerSearch, limit: 10 });
  const { data: leads } = useLeads({ search: leadSearch, status: 'qualified', limit: 10 });

  // Pre-select stage from URL
  useEffect(() => {
    const stageId = searchParams.get('stage_id');
    if (stageId && stages) {
      const stage = stages.find((s: PipelineStage) => s.id === parseInt(stageId));
      if (stage) {
        setFormData(prev => ({
          ...prev,
          stage_id: stage.id,
          probability: stage.probability,
        }));
      }
    }
  }, [searchParams, stages]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleStageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const stageId = parseInt(e.target.value);
    const stage = stages?.find((s: PipelineStage) => s.id === stageId);
    setFormData(prev => ({
      ...prev,
      stage_id: stageId || null,
      probability: stage?.probability || prev.probability,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (!formData.name) {
        throw new Error('Opportunity name is required');
      }

      const result = await createOpportunity(formData);
      router.push(`/sales/opportunities/${result.id}`);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create opportunity';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/sales/opportunities"
          className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div>
          <h1 className="text-2xl font-semibold text-foreground">New Opportunity</h1>
          <p className="text-sm text-slate-400 mt-1">Create a new deal in your pipeline</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-lg font-medium text-foreground mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-emerald-400" />
            Opportunity Details
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm text-slate-400 mb-2">Opportunity Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="Enterprise License Deal - Acme Corp"
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-slate-400 mb-2">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                placeholder="Describe this opportunity..."
                rows={3}
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
          </div>
        </div>

        {/* Customer/Lead Selection */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-lg font-medium text-foreground mb-4 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-emerald-400" />
            Customer / Lead
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Customer</label>
              <select
                name="customer_id"
                value={formData.customer_id || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, customer_id: parseInt(e.target.value) || null, lead_id: null }))}
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              >
                <option value="">Select customer...</option>
                {customers?.items?.map((customer: any) => (
                  <option key={customer.id} value={customer.id}>{customer.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Or Lead</label>
              <select
                name="lead_id"
                value={formData.lead_id || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, lead_id: parseInt(e.target.value) || null, customer_id: null }))}
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              >
                <option value="">Select lead...</option>
                {leads?.items?.map((lead: Lead) => (
                  <option key={lead.id} value={lead.id}>{lead.lead_name || lead.company_name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Pipeline & Value */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-lg font-medium text-foreground mb-4 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            Pipeline & Value
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Pipeline Stage</label>
              <select
                name="stage_id"
                value={formData.stage_id || ''}
                onChange={handleStageChange}
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              >
                <option value="">Select stage...</option>
                {stages?.filter((s: PipelineStage) => !s.is_won && !s.is_lost).map((stage: PipelineStage) => (
                  <option key={stage.id} value={stage.id}>{stage.name} ({stage.probability}%)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Expected Close Date</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="date"
                  name="expected_close_date"
                  value={formData.expected_close_date}
                  onChange={handleChange}
                  className="w-full pl-10 pr-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Deal Value</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="number"
                  name="deal_value"
                  value={formData.deal_value}
                  onChange={handleChange}
                  placeholder="0.00"
                  className="w-full pl-10 pr-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Probability (%)</label>
              <div className="relative">
                <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="number"
                  name="probability"
                  value={formData.probability}
                  onChange={handleChange}
                  min="0"
                  max="100"
                  className="w-full pl-10 pr-4 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                />
              </div>
            </div>
          </div>

          {formData.deal_value > 0 && formData.probability > 0 && (
            <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <div className="text-sm text-slate-400">Weighted Value</div>
              <div className="text-lg font-semibold text-emerald-400">
                {new Intl.NumberFormat('en-NG', {
                  style: 'currency',
                  currency: 'NGN',
                }).format((formData.deal_value * formData.probability) / 100)}
              </div>
            </div>
          )}
        </div>

        {/* Source */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-lg font-medium text-foreground mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-400" />
            Source
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Source</label>
              <input
                type="text"
                name="source"
                value={formData.source}
                onChange={handleChange}
                placeholder="Website, Referral, etc."
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Campaign</label>
              <input
                type="text"
                name="campaign"
                value={formData.campaign}
                onChange={handleChange}
                placeholder="Q4 2025 Promotion"
                className="w-full px-3 py-2 bg-slate-700/50 border border-slate-600 rounded-lg text-foreground placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-4">
          <Link
            href="/sales/opportunities"
            className="px-4 py-2 text-slate-400 hover:text-foreground transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-foreground rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {isSubmitting ? 'Creating...' : 'Create Opportunity'}
          </button>
        </div>
      </form>
    </div>
  );
}
