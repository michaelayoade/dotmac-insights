"use client";

import { useState } from "react";
import {
  Settings,
  Save,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function AssetSettingsPage() {
  const [settings, setSettings] = useState({
    default_depreciation_method: "straight_line",
    auto_post_depreciation: false,
    enable_cwip_by_default: false,
    default_finance_book: "",
    depreciation_posting_date: "last_day",
    maintenance_alert_days: 7,
    warranty_alert_days: 30,
    insurance_alert_days: 30,
  });

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    // Placeholder for API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Asset Settings</h1>
          <p className="text-sm text-slate-muted mt-1">
            Configure default behaviors for asset management
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
        >
          {saving ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Changes
        </button>
      </div>

      {/* Depreciation Settings */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="font-semibold text-white mb-4">Depreciation</h3>
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Default Depreciation Method</label>
              <select
                value={settings.default_depreciation_method}
                onChange={(e) => setSettings((s) => ({ ...s, default_depreciation_method: e.target.value }))}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              >
                <option value="straight_line">Straight Line</option>
                <option value="double_declining_balance">Double Declining Balance</option>
                <option value="written_down_value">Written Down Value</option>
                <option value="manual">Manual</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1">Default Finance Book</label>
              <input
                type="text"
                value={settings.default_finance_book}
                onChange={(e) => setSettings((s) => ({ ...s, default_finance_book: e.target.value }))}
                placeholder="Leave empty for default"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Depreciation Posting Date</label>
              <select
                value={settings.depreciation_posting_date}
                onChange={(e) => setSettings((s) => ({ ...s, depreciation_posting_date: e.target.value }))}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              >
                <option value="last_day">Last Day of Period</option>
                <option value="first_day">First Day of Period</option>
                <option value="schedule_date">Schedule Date</option>
              </select>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="auto_post"
                checked={settings.auto_post_depreciation}
                onChange={(e) => setSettings((s) => ({ ...s, auto_post_depreciation: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated focus:ring-indigo-500"
              />
              <label htmlFor="auto_post" className="text-sm text-slate-muted">
                Auto-post depreciation entries
              </label>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="cwip"
              checked={settings.enable_cwip_by_default}
              onChange={(e) => setSettings((s) => ({ ...s, enable_cwip_by_default: e.target.checked }))}
              className="w-4 h-4 rounded border-slate-border bg-slate-elevated focus:ring-indigo-500"
            />
            <label htmlFor="cwip" className="text-sm text-slate-muted">
              Enable CWIP Accounting by default for new categories
            </label>
          </div>
        </div>
      </div>

      {/* Alert Settings */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <h3 className="font-semibold text-white mb-4">Alert Thresholds</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-slate-muted mb-1">Maintenance Alert (days)</label>
            <input
              type="number"
              min="1"
              max="365"
              value={settings.maintenance_alert_days}
              onChange={(e) => setSettings((s) => ({ ...s, maintenance_alert_days: parseInt(e.target.value) || 7 }))}
              className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-1">Warranty Alert (days)</label>
            <input
              type="number"
              min="1"
              max="365"
              value={settings.warranty_alert_days}
              onChange={(e) => setSettings((s) => ({ ...s, warranty_alert_days: parseInt(e.target.value) || 30 }))}
              className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-1">Insurance Alert (days)</label>
            <input
              type="number"
              min="1"
              max="365"
              value={settings.insurance_alert_days}
              onChange={(e) => setSettings((s) => ({ ...s, insurance_alert_days: parseInt(e.target.value) || 30 }))}
              className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-300">Note</p>
            <p className="text-sm text-slate-muted mt-1">
              Changes to depreciation settings will only affect newly created assets.
              Existing assets will retain their current depreciation configuration.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
