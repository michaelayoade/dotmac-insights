'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Save,
  TestTube,
  Loader2,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
} from 'lucide-react';
import Link from 'next/link';
import { useSettings, useSettingsSchema, useSettingsMutations } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

const GROUP_LABELS: Record<string, string> = {
  email: 'Email Configuration',
  payments: 'Payment Gateway',
  webhooks: 'Outgoing Webhooks',
  sms: 'SMS Configuration',
  notifications: 'Notification Preferences',
  branding: 'Company Branding',
  localization: 'Localization',
};

export default function SettingsGroupPage() {
  const params = useParams();
  const router = useRouter();
  const group = params.group as string;

  const { data: settings, isLoading: settingsLoading } = useSettings(group);
  const { data: schemaData, isLoading: schemaLoading } = useSettingsSchema(group);
  const { update, test, getTestStatus } = useSettingsMutations();

  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: 'success' | 'failed';
    message?: string;
    error?: string;
  } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (settings?.data) {
      setFormData(settings.data);
    }
  }, [settings]);

  const handleChange = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setSaveError(null);
    setTestResult(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await update(group, formData);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { job_id } = await test(group, formData);

      // Poll for result
      let attempts = 0;
      const maxAttempts = 60; // 30 seconds
      while (attempts < maxAttempts) {
        await new Promise((r) => setTimeout(r, 500));
        const status = await getTestStatus(job_id);

        if (status.status === 'success') {
          setTestResult({
            status: 'success',
            message: (status.result as Record<string, unknown>)?.message as string || 'Test passed',
          });
          break;
        } else if (status.status === 'failed') {
          setTestResult({
            status: 'failed',
            error: status.error || 'Test failed',
          });
          break;
        }
        attempts++;
      }

      if (attempts >= maxAttempts) {
        setTestResult({
          status: 'failed',
          error: 'Test timed out',
        });
      }
    } catch (err: unknown) {
      setTestResult({
        status: 'failed',
        error: err instanceof Error ? err.message : 'Test failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const toggleSecret = (field: string) => {
    setShowSecrets((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const isLoading = settingsLoading || schemaLoading;
  const schema = schemaData?.schema;
  const secretFields = new Set(schemaData?.secret_fields || []);

  const canTest = ['email', 'payments', 'sms', 'webhooks'].includes(group);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <div className="h-8 w-32 bg-slate-700 rounded animate-pulse" />
        </div>
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-24 bg-slate-700 rounded" />
                <div className="h-10 w-full bg-slate-700 rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const properties = schema?.properties || {};

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/settings"
            className="p-2 rounded-lg hover:bg-slate-elevated transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-slate-muted" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">
              {GROUP_LABELS[group] || group}
            </h1>
            <p className="text-slate-muted text-sm">
              {schema?.description || `Configure ${group} settings`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {canTest && (
            <button
              onClick={handleTest}
              disabled={testing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-white text-sm font-medium hover:bg-slate-elevated disabled:opacity-50 transition-colors"
            >
              {testing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <TestTube className="w-4 h-4" />
              )}
              Test
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 text-sm font-semibold hover:bg-teal-electric/90 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save Changes
          </button>
        </div>
      </header>

      {/* Test Result */}
      {testResult && (
        <div
          className={cn(
            'flex items-center gap-3 p-4 rounded-lg border',
            testResult.status === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'
          )}
        >
          {testResult.status === 'success' ? (
            <CheckCircle className="w-5 h-5" />
          ) : (
            <XCircle className="w-5 h-5" />
          )}
          <span>{testResult.message || testResult.error}</span>
        </div>
      )}

      {/* Save Error */}
      {saveError && (
        <div className="flex items-center gap-3 p-4 rounded-lg border bg-red-500/10 border-red-500/30 text-red-300">
          <XCircle className="w-5 h-5" />
          <span>{saveError}</span>
        </div>
      )}

      {/* Settings Form */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <div className="space-y-6">
          {Object.entries(properties).map(([fieldName, fieldSchema]) => {
            const value = formData[fieldName];
            const isSecret = secretFields.has(fieldName);
            const showValue = !isSecret || showSecrets[fieldName];

            return (
              <div key={fieldName} className="space-y-2">
                <label className="block text-sm font-medium text-slate-200">
                  {fieldName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  {schema?.required?.includes(fieldName) && (
                    <span className="text-red-400 ml-1">*</span>
                  )}
                </label>

                {fieldSchema.description && (
                  <p className="text-xs text-slate-muted">{fieldSchema.description}</p>
                )}

                {fieldSchema.type === 'boolean' ? (
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!value}
                      onChange={(e) => handleChange(fieldName, e.target.checked)}
                      className="w-5 h-5 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric"
                    />
                    <span className="text-sm text-slate-300">
                      {value ? 'Enabled' : 'Disabled'}
                    </span>
                  </label>
                ) : fieldSchema.enum ? (
                  <select
                    value={(value as string) || ''}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none"
                  >
                    <option value="">Select...</option>
                    {fieldSchema.enum.map((opt: string) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : fieldSchema.type === 'integer' ? (
                  <input
                    type="number"
                    value={(value as number) ?? ''}
                    onChange={(e) =>
                      handleChange(fieldName, e.target.value ? parseInt(e.target.value, 10) : null)
                    }
                    min={fieldSchema.minimum}
                    max={fieldSchema.maximum}
                    className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none"
                  />
                ) : (
                  <div className="relative">
                    <input
                      type={isSecret && !showValue ? 'password' : 'text'}
                      value={(value as string) || ''}
                      onChange={(e) => handleChange(fieldName, e.target.value)}
                      placeholder={isSecret ? '***REDACTED***' : ''}
                      className="w-full px-3 py-2 rounded-lg bg-slate-elevated border border-slate-border text-white text-sm focus:border-teal-electric focus:outline-none pr-10"
                    />
                    {isSecret && (
                      <button
                        type="button"
                        onClick={() => toggleSecret(fieldName)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-muted hover:text-white"
                      >
                        {showValue ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
