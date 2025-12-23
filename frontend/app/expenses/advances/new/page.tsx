"use client";

import { useState, useMemo } from "react";
import { useCashAdvanceMutations } from "@/hooks/useExpenses";
import { useEmployees } from "@/hooks/useApi";
import { EmployeeSearch } from "@/components/EntitySearch";
import type { CashAdvanceCreatePayload } from "@/lib/expenses.types";
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

const todayISO = () => new Date().toISOString().slice(0, 10);
const addDaysISO = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export default function NewCashAdvancePage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:write');
  const { createAdvance } = useCashAdvanceMutations();
  const canFetch = !authLoading && !missingScope;
  const { data: employeesData, isLoading: employeesLoading } = useEmployees({ limit: 200 }, { isPaused: () => !canFetch });
  const employees = useMemo(() => employeesData?.items || [], [employeesData]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<{ id: number; name: string } | null>(null);

  const [form, setForm] = useState<Omit<CashAdvanceCreatePayload, 'employee_id'>>({
    purpose: "",
    request_date: todayISO(),
    required_by_date: addDaysISO(3),
    project_id: undefined,
    trip_start_date: undefined,
    trip_end_date: undefined,
    destination: "",
    requested_amount: 0,
    currency: "NGN",
    base_currency: "NGN",
    conversion_rate: 1,
    company: "",
  });

  const handleSubmit = async () => {
    setError(null);
    setSuccess(null);
    if (!selectedEmployee || !form.purpose || !form.requested_amount) {
      setError("Employee, purpose, and requested amount are required.");
      return;
    }
    setSubmitting(true);
    try {
      await createAdvance({
        ...form,
        employee_id: selectedEmployee.id,
      } as CashAdvanceCreatePayload);
      setSuccess("Cash advance created.");
    } catch (e: any) {
      setError(e?.message || "Failed to create cash advance");
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
        message="You need the expenses:write permission to create cash advances."
        backHref="/expenses/advances"
        backLabel="Back to Advances"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-foreground">New Cash Advance</h2>
        <p className="text-sm text-slate-muted">Request pre-funding for expenses.</p>
      </div>

      <div className="grid gap-4 rounded-xl border border-slate-border bg-slate-card p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <EmployeeSearch
            label="Employee"
            employees={employees}
            value={selectedEmployee}
            onSelect={setSelectedEmployee}
            loading={employeesLoading}
            required
          />
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Purpose</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.purpose}
              onChange={(e) => setForm((prev) => ({ ...prev, purpose: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Request Date</span>
            <input
              type="date"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.request_date}
              onChange={(e) => setForm((prev) => ({ ...prev, request_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Required By</span>
            <input
              type="date"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.required_by_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, required_by_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Requested Amount</span>
            <input
              type="number"
              step="0.01"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.requested_amount}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, requested_amount: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Currency</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.currency || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
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
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Destination</span>
            <input
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.destination || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, destination: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Trip Start</span>
            <input
              type="date"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.trip_start_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, trip_start_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-muted">Trip End</span>
            <input
              type="date"
              className="rounded-lg border border-slate-border bg-slate-elevated px-3 py-2 text-foreground"
              value={form.trip_end_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, trip_end_date: e.target.value }))}
            />
          </label>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-teal-electric px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm hover:bg-teal-electric/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Saving..." : "Create Advance"}
        </Button>
        {error && <span className="text-sm text-red-400">{error}</span>}
        {success && <span className="text-sm text-green-400">{success}</span>}
      </div>
    </div>
  );
}