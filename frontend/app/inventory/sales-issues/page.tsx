"use client";

import Link from "next/link";
import {
  ArrowUpFromLine,
  Plus,
  FileText,
  ArrowRight,
  Package,
  BookOpen,
  TrendingUp,
} from "lucide-react";

export default function SalesIssuesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Sales Issues</h1>
          <p className="text-slate-muted text-sm">Issue stock for sales invoices and record COGS</p>
        </div>
        <Link
          href="/books/accounts-receivable/invoices"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          From Invoice
        </Link>
      </div>

      {/* Workflow Explanation */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Sales Issue Workflow</h2>

        <div className="flex flex-col md:flex-row items-start md:items-center gap-4 mb-6">
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-blue-500/20">
              <FileText className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">1. Create Invoice</p>
              <p className="text-xs text-slate-muted">Record sales invoice</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-amber-500/20">
              <ArrowUpFromLine className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">2. Issue Stock</p>
              <p className="text-xs text-slate-muted">Create stock issue</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-red-500/20">
              <Package className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">3. Reduce Inventory</p>
              <p className="text-xs text-slate-muted">Stock ledger updated</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <BookOpen className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">4. Post COGS</p>
              <p className="text-xs text-slate-muted">DR COGS, CR Inventory</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-border pt-4">
          <h3 className="text-sm font-medium text-foreground mb-2">GL Entries Created</h3>
          <div className="bg-slate-elevated rounded-lg p-3 font-mono text-xs">
            <div className="flex justify-between text-slate-muted border-b border-slate-border/50 pb-2 mb-2">
              <span>Account</span>
              <span className="flex gap-8"><span>Debit</span><span>Credit</span></span>
            </div>
            <div className="flex justify-between text-foreground">
              <span>5100 - Cost of Goods Sold</span>
              <span className="flex gap-8"><span>XXX.XX</span><span>-</span></span>
            </div>
            <div className="flex justify-between text-foreground">
              <span>1310 - Inventory Asset</span>
              <span className="flex gap-8"><span>-</span><span>XXX.XX</span></span>
            </div>
          </div>
        </div>
      </div>

      {/* Impact Summary */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Financial Impact
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="text-xs text-slate-muted mb-1">Inventory Asset</p>
            <p className="text-foreground font-medium">Decreases by cost value</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="text-xs text-slate-muted mb-1">Cost of Goods Sold</p>
            <p className="text-foreground font-medium">Increases (expense)</p>
          </div>
          <div className="bg-slate-elevated rounded-lg p-3">
            <p className="text-xs text-slate-muted mb-1">Gross Profit</p>
            <p className="text-foreground font-medium">Revenue minus COGS</p>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/books/accounts-receivable/invoices"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:bg-slate-elevated transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20 group-hover:bg-blue-500/30">
              <FileText className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">View Invoices</p>
              <p className="text-xs text-slate-muted">Go to Accounts Receivable to see invoices</p>
            </div>
          </div>
        </Link>
        <Link
          href="/inventory/stock-entries?type=Material%20Issue"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:bg-slate-elevated transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20 group-hover:bg-amber-500/30">
              <ArrowUpFromLine className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-foreground font-medium">View Issues</p>
              <p className="text-xs text-slate-muted">See material issue stock entries</p>
            </div>
          </div>
        </Link>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
        <p className="text-amber-300 text-sm">
          <strong>Note:</strong> Sales issues are created from invoices in Books &gt; Accounts Receivable.
          The stock entry is automatically created when you post an invoice with inventory items.
        </p>
      </div>
    </div>
  );
}
