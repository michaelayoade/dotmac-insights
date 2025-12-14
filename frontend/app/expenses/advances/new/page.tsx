"use client";

import { useState } from "react";
import dayjs from "dayjs";
import { useCashAdvanceMutations } from "@/hooks/useExpenses";
import type { CashAdvanceCreatePayload } from "@/lib/expenses.types";

export default function NewCashAdvancePage() {
  const { createAdvance } = useCashAdvanceMutations();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [form, setForm] = useState<CashAdvanceCreatePayload>({
    employee_id: 0,
    purpose: "",
    request_date: dayjs().format("YYYY-MM-DD"),
    required_by_date: dayjs().add(3, "day").format("YYYY-MM-DD"),
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
    if (!form.employee_id || !form.purpose || !form.requested_amount) {
      setError("Employee, purpose, and requested amount are required.");
      return;
    }
    setSubmitting(true);
    try {
      await createAdvance(form);
      setSuccess("Cash advance created.");
    } catch (e: any) {
      setError(e?.message || "Failed to create cash advance");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">New Cash Advance</h2>
        <p className="text-sm text-gray-500">Request pre-funding for expenses.</p>
      </div>

      <div className="grid gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
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
            Purpose
            <input
              className="rounded-lg border px-3 py-2"
              value={form.purpose}
              onChange={(e) => setForm((prev) => ({ ...prev, purpose: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Request Date
            <input
              type="date"
              className="rounded-lg border px-3 py-2"
              value={form.request_date}
              onChange={(e) => setForm((prev) => ({ ...prev, request_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Required By
            <input
              type="date"
              className="rounded-lg border px-3 py-2"
              value={form.required_by_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, required_by_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Requested Amount
            <input
              type="number"
              step="0.01"
              className="rounded-lg border px-3 py-2"
              value={form.requested_amount}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, requested_amount: Number(e.target.value) || 0 }))
              }
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Currency
            <input
              className="rounded-lg border px-3 py-2"
              value={form.currency || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}
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
          <label className="flex flex-col gap-1 text-sm">
            Destination
            <input
              className="rounded-lg border px-3 py-2"
              value={form.destination || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, destination: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Trip Start
            <input
              type="date"
              className="rounded-lg border px-3 py-2"
              value={form.trip_start_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, trip_start_date: e.target.value }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Trip End
            <input
              type="date"
              className="rounded-lg border px-3 py-2"
              value={form.trip_end_date || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, trip_end_date: e.target.value }))}
            />
          </label>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {submitting ? "Saving..." : "Create Advance"}
        </button>
        {error && <span className="text-sm text-red-600">{error}</span>}
        {success && <span className="text-sm text-green-600">{success}</span>}
      </div>
    </div>
  );
}
