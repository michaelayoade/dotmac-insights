"use client";

import Link from "next/link";
import {
  ArrowDownToLine,
  Plus,
  FileText,
  ArrowRight,
  Package,
  BookOpen,
} from "lucide-react";

export default function PurchaseReceiptsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Purchase Receipts</h1>
          <p className="text-slate-muted text-sm">Receive stock from purchase bills into inventory</p>
        </div>
        <Link
          href="/books/accounts-payable/bills"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold hover:bg-amber-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          From Bill
        </Link>
      </div>

      {/* Workflow Explanation */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Purchase Receipt Workflow</h2>

        <div className="flex flex-col md:flex-row items-start md:items-center gap-4 mb-6">
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-blue-500/20">
              <FileText className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-white font-medium">1. Create Bill</p>
              <p className="text-xs text-slate-muted">Record purchase invoice</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-amber-500/20">
              <ArrowDownToLine className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-white font-medium">2. Receive Stock</p>
              <p className="text-xs text-slate-muted">Create stock receipt</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-emerald-500/20">
              <Package className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-white font-medium">3. Update Inventory</p>
              <p className="text-xs text-slate-muted">Stock ledger updated</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-slate-muted hidden md:block" />
          <div className="flex items-center gap-3 bg-slate-elevated rounded-lg p-3 flex-1">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <BookOpen className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-white font-medium">4. Post to GL</p>
              <p className="text-xs text-slate-muted">DR Inventory, CR GRNI</p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-border pt-4">
          <h3 className="text-sm font-medium text-white mb-2">GL Entries Created</h3>
          <div className="bg-slate-elevated rounded-lg p-3 font-mono text-xs">
            <div className="flex justify-between text-slate-muted border-b border-slate-border/50 pb-2 mb-2">
              <span>Account</span>
              <span className="flex gap-8"><span>Debit</span><span>Credit</span></span>
            </div>
            <div className="flex justify-between text-white">
              <span>1310 - Inventory Asset</span>
              <span className="flex gap-8"><span>XXX.XX</span><span>-</span></span>
            </div>
            <div className="flex justify-between text-white">
              <span>2110 - Goods Received Not Invoiced</span>
              <span className="flex gap-8"><span>-</span><span>XXX.XX</span></span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/books/accounts-payable/bills"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:bg-slate-elevated transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20 group-hover:bg-blue-500/30">
              <FileText className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-white font-medium">View Bills</p>
              <p className="text-xs text-slate-muted">Go to Accounts Payable to see bills</p>
            </div>
          </div>
        </Link>
        <Link
          href="/inventory/stock-entries?type=Material%20Receipt"
          className="bg-slate-card border border-slate-border rounded-xl p-4 hover:bg-slate-elevated transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20 group-hover:bg-amber-500/30">
              <ArrowDownToLine className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-white font-medium">View Receipts</p>
              <p className="text-xs text-slate-muted">See material receipt stock entries</p>
            </div>
          </div>
        </Link>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
        <p className="text-amber-300 text-sm">
          <strong>Note:</strong> Purchase receipts are created from bills in Books &gt; Accounts Payable.
          The stock entry is automatically created when you post a bill with inventory items.
        </p>
      </div>
    </div>
  );
}
