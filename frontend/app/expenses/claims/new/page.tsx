"use client";

import { useMemo, useState } from "react";
import dayjs from "dayjs";
import { useExpenseCategories, useExpenseMutations } from "@/hooks/useExpenses";
import type { ExpenseClaimCreatePayload, ExpenseClaimLinePayload } from "@/lib/expenses.types";

type FundingMethod = ExpenseClaimLinePayload["funding_method"];

const defaultLine = (): ExpenseClaimLinePayload => ({
  category_id: 0,
  expense_date: dayjs().format("YYYY-MM-DD"),
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
  const { data: categories } = useExpenseCategories({ include_inactive: false });
  const { createClaim } = useExpenseMutations();

  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<ExpenseClaimCreatePayload>({
    title: "",
    description: "",
    employee_id: 0,
    claim_date: dayjs().format("YYYY-MM-DD"),
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
    if (!form.title || !form.employee_id || !form.lines.length) {
      setError("Title, employee, and at least one line are required.");
      return;
    }
    if (form.lines.some((l) => !l.category_id || !l.description || !l.expense_date)) {
      setError("Each line needs category, description, and date.");
      return;
    }
    setSubmitting(true);
    try {
      await createClaim(form);
      setSuccess("Expense claim created.");
    } catch (e: any) {
      setError(e?.message || "Failed to create claim");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">New Expense Claim</h2>
        <p className="text-sm text-gray-500">Capture claim header and detailed lines.</p>
      </div>

      <div className="grid gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              className="rounded-lg border px-3 py-2"
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Employee ID
            <input
              type="number"
              className="rounded-lg border px-3 py-2"
              value={form.employee_id || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, employee_id: Number(e.target.value) }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Claim Date
            <input
              type="date"
              className="rounded-lg border px-3 py-2"
              value={form.claim_date}
              onChange={(e) => setForm((prev) => ({ ...prev, claim_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Currency
            <input
              className="rounded-lg border px-3 py-2"
              value={form.currency}
              onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Base Currency
            <input
              className="rounded-lg border px-3 py-2"
              value={form.base_currency}
              onChange={(e) => setForm((prev) => ({ ...prev, base_currency: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Conversion Rate
            <input
              type="number"
              step="0.0001"
              className="rounded-lg border px-3 py-2"
              value={form.conversion_rate}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, conversion_rate: Number(e.target.value) || 1 }))
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm md:col-span-2">
            Description
            <textarea
              className="rounded-lg border px-3 py-2"
              value={form.description || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            />
          </label>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Line Items</h3>
          <button
            onClick={addLine}
            className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700"
          >
            Add line
          </button>
        </div>

        <div className="space-y-4">
          {form.lines.map((line, idx) => (
            <div key={idx} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <label className="flex flex-col gap-1 text-sm">
                    Category
                    <select
                      className="rounded-lg border px-3 py-2"
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
                    Expense Date
                    <input
                      type="date"
                      className="rounded-lg border px-3 py-2"
                      value={line.expense_date}
                      onChange={(e) => updateLine(idx, { expense_date: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    Funding Method
                    <select
                      className="rounded-lg border px-3 py-2"
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
                    Description
                    <input
                      className="rounded-lg border px-3 py-2"
                      value={line.description}
                      onChange={(e) => updateLine(idx, { description: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    Amount
                    <input
                      type="number"
                      step="0.01"
                      className="rounded-lg border px-3 py-2"
                      value={line.claimed_amount}
                      onChange={(e) => updateLine(idx, { claimed_amount: Number(e.target.value) || 0 })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    Currency
                    <input
                      className="rounded-lg border px-3 py-2"
                      value={line.currency || ""}
                      onChange={(e) => updateLine(idx, { currency: e.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    Receipt?
                    <select
                      className="rounded-lg border px-3 py-2"
                      value={line.has_receipt ? "yes" : "no"}
                      onChange={(e) => updateLine(idx, { has_receipt: e.target.value === "yes" })}
                    >
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </select>
                  </label>
                  {!line.has_receipt && (
                    <label className="flex flex-col gap-1 text-sm md:col-span-2">
                      Missing Receipt Reason
                      <input
                        className="rounded-lg border px-3 py-2"
                        value={line.receipt_missing_reason || ""}
                        onChange={(e) => updateLine(idx, { receipt_missing_reason: e.target.value })}
                      />
                    </label>
                  )}
                </div>
                <button
                  className="text-sm text-red-600 underline"
                  onClick={() => removeLine(idx)}
                  disabled={form.lines.length === 1}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {submitting ? "Saving..." : "Create Claim"}
        </button>
        {error && <span className="text-sm text-red-600">{error}</span>}
        {success && <span className="text-sm text-green-600">{success}</span>}
      </div>
    </div>
  );
}
