"use client";

import { Settings, Save } from "lucide-react";

export default function InventorySettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Inventory Settings</h1>
        <p className="text-slate-muted text-sm">Configure inventory management preferences</p>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-6 space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Valuation Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1.5">Default Valuation Method</label>
              <select
                disabled
                className="w-full max-w-xs px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white opacity-50"
              >
                <option value="FIFO">FIFO (First In First Out)</option>
                <option value="LIFO">LIFO (Last In First Out)</option>
                <option value="moving_average">Moving Average</option>
              </select>
              <p className="text-xs text-slate-muted mt-1">Applied to new items by default</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-border pt-6">
          <h2 className="text-lg font-semibold text-white mb-4">Warehouse Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1.5">Default Warehouse</label>
              <select
                disabled
                className="w-full max-w-xs px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white opacity-50"
              >
                <option value="">Select warehouse...</option>
              </select>
              <p className="text-xs text-slate-muted mt-1">Default warehouse for new stock entries</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-border pt-6">
          <h2 className="text-lg font-semibold text-white mb-4">GL Integration</h2>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                disabled
                className="w-4 h-4 rounded border-slate-border bg-slate-elevated opacity-50"
              />
              <div>
                <span className="text-sm text-white">Auto-post to General Ledger</span>
                <p className="text-xs text-slate-muted">Automatically create journal entries for stock movements</p>
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1.5">Stock Asset Account</label>
              <select
                disabled
                className="w-full max-w-xs px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white opacity-50"
              >
                <option value="">Select account...</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-1.5">COGS Account</label>
              <select
                disabled
                className="w-full max-w-xs px-3 py-2 rounded-lg border border-slate-border bg-slate-elevated text-white opacity-50"
              >
                <option value="">Select account...</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 pt-4">
          <button
            disabled
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold opacity-50 cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            Save Settings
          </button>
          <span className="text-amber-400 text-sm">Coming soon</span>
        </div>
      </div>
    </div>
  );
}
