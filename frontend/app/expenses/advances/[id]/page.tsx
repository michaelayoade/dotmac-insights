"use client";

import { useParams } from "next/navigation";
import { useCashAdvanceDetail, useCashAdvanceMutations } from "@/hooks/useExpenses";
import { formatDate } from "@/lib/utils";
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function CashAdvanceDetailPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const params = useParams<{ id: string }>();
  const advanceId = Number(params?.id);
  const canFetch = !authLoading && !missingScope;
  const { data, error } = useCashAdvanceDetail(advanceId, { isPaused: () => !canFetch });
  const { submitAdvance, approveAdvance, rejectAdvance, disburseAdvance, settleAdvance } = useCashAdvanceMutations();

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view cash advances."
        backHref="/expenses/advances"
        backLabel="Back to Advances"
      />
    );
  }

  if (error) return <div className="text-red-600">Failed to load cash advance</div>;
  if (!data) return <div>Loading cash advance...</div>;

  const actions = [];
  if (data.status === "draft") {
    actions.push(<Button key="submit" onClick={() => submitAdvance(data.id)} className="rounded-lg bg-blue-600 px-3 py-2 text-foreground">Submit</Button>);
  }
  if (data.status === "pending_approval") {
    actions.push(<Button key="approve" onClick={() => approveAdvance(data.id)} className="rounded-lg bg-green-600 px-3 py-2 text-foreground">Approve</Button>);
    actions.push(
      <Button
        key="reject"
        onClick={() => {
          const reason = prompt("Enter rejection reason");
          if (reason) rejectAdvance(data.id, reason);
        }}
        className="rounded-lg bg-red-600 px-3 py-2 text-foreground"
      >
        Reject
      </Button>
    );
  }
  if (data.status === "approved" || data.status === "pending_approval") {
    actions.push(
      <Button
        key="disburse"
        onClick={() => {
          const amountStr = prompt("Disburse amount", String(data.requested_amount));
          if (!amountStr) return;
          const amount = Number(amountStr);
          disburseAdvance(data.id, { amount });
        }}
        className="rounded-lg bg-indigo-600 px-3 py-2 text-foreground"
      >
        Disburse
      </Button>
    );
  }
  if (data.status === "disbursed" || data.status === "partially_settled") {
    actions.push(
      <Button
        key="settle"
        onClick={() => {
          const amountStr = prompt("Settle amount", "0");
          const refundStr = prompt("Refund amount (if any)", "0");
          if (amountStr === null || refundStr === null) return;
          settleAdvance(data.id, { amount: Number(amountStr), refund_amount: Number(refundStr) });
        }}
        className="rounded-lg bg-amber-600 px-3 py-2 text-foreground"
      >
        Settle
      </Button>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">
            {data.advance_number || `Draft #${data.id}`} <span className="text-sm text-gray-500">({data.status})</span>
          </h2>
          <p className="text-sm text-gray-500">
            Request Date: {formatDate(data.request_date)} · Employee: {data.employee_id}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>

      <div className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm text-sm text-gray-800">
        <div className="flex gap-4">
          <span className="font-semibold text-gray-900">Purpose:</span> {data.purpose}
        </div>
        <div className="flex gap-4">
          <span className="font-semibold text-gray-900">Requested:</span> {data.requested_amount.toLocaleString()} {data.currency}
        </div>
        <div className="flex gap-4">
          <span className="font-semibold text-gray-900">Disbursed:</span> {data.disbursed_amount.toLocaleString()} {data.currency}
        </div>
        <div className="flex gap-4">
          <span className="font-semibold text-gray-900">Outstanding:</span> {data.outstanding_amount.toLocaleString()} {data.currency}
        </div>
        {data.destination && (
          <div className="flex gap-4">
            <span className="font-semibold text-gray-900">Destination:</span> {data.destination}
          </div>
        )}
      </div>
    </div>
  );
}