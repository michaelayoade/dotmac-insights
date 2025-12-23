"use client";

import { useMemo, useState } from "react";
import { useExpenseCategories, useExpenseMutations } from "@/hooks/useExpenses";
import { useEmployees } from "@/hooks/useApi";
import { EmployeeSearch } from "@/components/EntitySearch";
import type { ExpenseClaimCreatePayload, ExpenseClaimLinePayload } from "@/lib/expenses.types";
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

type FundingMethod = ExpenseClaimLinePayload["funding_method"];

const todayISO = () => new Date().toISOString().slice(0, 10);

const defaultLine = (): ExpenseClaimLinePayload => ({
  category_id: 0,
  expense_date: todayISO(),
  description: "",
  claimed_amount: 0,
  currency: "NGN",
  tax_rate: 0,
  tax_amount: 0,
  conversion_rate: 1,
  funding_method: "out_of_pocket",
  has_receipt: false,
});

export default function NewExpenseClaimPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:write');
  const canFetch = !authLoading && !missingScope;
  const { data: categories } = useExpenseCategories({ include_inactive: false }, { isPaused: () => !canFetch });
  const { createClaim } = useExpenseMutations();
  const { data: employeesData, isLoading: employeesLoading } = useEmployees({ limit: 200 }, { isPaused: () => !canFetch });
  const employees = useMemo(() => employeesData?.items || [], [employeesData]);

  const [submitting, setSubmitting] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<{ id: number; name: string } | null>(null);
  const [form, setForm] = useState<Omit<ExpenseClaimCreatePayload, 'employee_id'>>({
    title: "",
    description: "",
    claim_date: todayISO(),
    currency: "NGN",
    base_currency: "NGN",
    conversion_rate: 1,
    project_id: undefined,
    cost_center: "",
    company: "",
    lines: [defaultLine()],
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const categoryOptions = useMemo(() => categories || [], [categories]);

  const updateLine = (idx: number, changes: Partial<ExpenseClaimLinePayload>) => {
    setForm((prev) => {
      const lines = prev.lines.slice();
      lines[idx] = { ...lines[idx], ...changes };
      return { ...prev, lines };
    });
  };

  const addLine = () => setForm((prev) => ({ ...prev, lines: [...prev.lines, defaultLine()] }));
  const removeLine = (idx: number) =>
    setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== idx) }));

  const handleSubmit = async () => {
    setError(null);
    setSuccess(null);
    // Basic validation
    if (!form.title || !selectedEmployee || !form.lines.length) {
      setError("Title, employee, and at least one line are required.");
      return;
    }
    if (form.lines.some((l) => !l.category_id || !l.description || !l.expense_date)) {
      setError("Each line needs category, description, and date.");
      return;
    }
    setSubmitting(true);
    try {
      await createClaim({
        ...form,
        employee_id: selectedEmployee.id,
      } as ExpenseClaimCreatePayload);
      setSuccess("Expense claim created.");
    } catch (e: any) {
      setError(e?.message || "Failed to create claim");
    } finally {
      setSubmitting(false);
    }
  };

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:write permission to create expense claims."
        backHref="/expenses/claims"
        backLabel="Back to Claims"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-foreground">New Expense Claim</h2>
        <p className="text-sm text-slate-muted">Capture claim header and detailed lines.</p>
      </div>

      <div className="grid gap-4 rounded-xl border border-slate-border bg-slate-card p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Title</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            />
          </label>
          <EmployeeSearch
            label="Employee"
            employees={employees}
            value={selectedEmployee}
            onSelect={setSelectedEmployee}
            loading={employeesLoading}
            required
          />
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Claim Date</span>
            <input
              type="date"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.claim_date}
              onChange={(e) => setForm((prev) => ({ ...prev, claim_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Currency</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.currency}
              onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Base Currency</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.base_currency}
              onChange={(e) => setForm((prev) => ({ ...prev, base_currency: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Conversion Rate</span>
            <input
              type="number"
              step="0.0001"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.conversion_rate}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, conversion_rate: Number(e.target.value) || 1 }))
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm md:col-span-2">
            <span className="text-slate-muted">Description</span>
            <textarea
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.description || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            />
          </label>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-foreground">Line Items</h3>
          <Button
            onClick={addLine}
            className="rounded-lg border border-teal-electric/30 bg-teal-electric/10 px-3 py-1 text-sm font-medium text-teal-electric"
          >
            Add line
          </Button>
        </div>

        <div className="space-y-4">
          {form.lines.map((line, idx) => (
            <div key={idx} className="rounded-xl border border-slate-border bg-slate-card p-4 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="grid gap-3 md:grid-cols-3 flex-1">
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Category</span>
                    <select
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.category_id || 0}
                      onChange={(e) => updateLine(idx, { category_id: Number(e.target.value) })}
                    >
                      <option value={0}>Select category</option>
                      {categoryOptions.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Expense Date</span>
                    <input
                      type="date"
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.expense_date}
                      onChange={(e) => updateLine(idx, { expense_date: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Funding Method</span>
                    <select
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.funding_method}
                      onChange={(e) => updateLine(idx, { funding_method: e.target.value as FundingMethod })}
                    >
                      <option value="out_of_pocket">Out of Pocket</option>
                      <option value="cash_advance">Cash Advance</option>
                      <option value="corporate_card">Corporate Card</option>
                      <option value="per_diem">Per Diem</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-sm md:col-span-2">
                    <span className="text-slate-muted">Description</span>
                    <input
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.description}
                      onChange={(e) => updateLine(idx, { description: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Amount</span>
                    <input
                      type="number"
                      step="0.01"
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.claimed_amount}
                      onChange={(e) => updateLine(idx, { claimed_amount: Number(e.target.value) || 0 })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Currency</span>
                    <input
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.currency || ""}
                      onChange={(e) => updateLine(idx, { currency: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="text-slate-muted">Receipt?</span>
                    <select
                      className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                      value={line.has_receipt ? "yes" : "no"}
                      onChange={(e) => updateLine(idx, { has_receipt: e.target.value === "yes" })}
                    >
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </select>
                  </label>
                  {!line.has_receipt && (
                    <label className="flex flex-col gap-1 text-sm md:col-span-2">
                      <span className="text-slate-muted">Missing Receipt Reason</span>
                      <input
                        className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
                        value={line.receipt_missing_reason || ""}
                        onChange={(e) => updateLine(idx, { receipt_missing_reason: e.target.value })}
                      />
                    </label>
                  )}
                </div>
                <Button
                  className="text-sm text-red-400 underline"
                  onClick={() => removeLine(idx)}
                  disabled={form.lines.length === 1}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-teal-electric px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm hover:bg-teal-electric/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Saving..." : "Create Claim"}
        </Button>
        {error && <span className="text-sm text-red-400">{error}</span>}
        {success && <span className="text-sm text-green-400">{success}</span>}
      </div>
    </div>
  );
}