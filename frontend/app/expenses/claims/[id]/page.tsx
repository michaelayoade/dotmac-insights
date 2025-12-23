"use client";

import { useParams } from "next/navigation";
import { useExpenseClaimDetail, useExpenseMutations } from "@/hooks/useExpenses";
import { formatDate } from "@/lib/utils";
import { LoadingState, Button } from '@/components/ui';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

export default function ExpenseClaimDetailPage() {
  // All hooks must be called unconditionally at the top
  const { isLoading: authLoading, missingScope } = useRequireScope('expenses:read');
  const params = useParams<{ id: string }>();
  const claimId = Number(params?.id);
  const canFetch = !authLoading && !missingScope;
  const { data, error } = useExpenseClaimDetail(claimId, { isPaused: () => !canFetch });
  const { submitClaim, approveClaim, rejectClaim, postClaim, reverseClaim } = useExpenseMutations();

  // Permission guard - after all hooks
  if (authLoading) {
    return <LoadingState message="Checking permissions..." />;
  }
  if (missingScope) {
    return (
      <AccessDenied
        message="You need the expenses:read permission to view expense claims."
        backHref="/expenses/claims"
        backLabel="Back to Claims"
      />
    );
  }

  if (error) return <div className="text-red-600">Failed to load claim</div>;
  if (!data) return <div>Loading claim...</div>;

  const actions = [];
  if (data.status === "draft" || data.status === "returned" || data.status === "recalled") {
    actions.push(<Button key="submit" onClick={() => submitClaim(data.id)} className="rounded-lg bg-blue-600 px-3 py-2 text-foreground">Submit</Button>);
  }
  if (data.status === "pending_approval") {
    actions.push(<Button key="approve" onClick={() => approveClaim(data.id)} className="rounded-lg bg-green-600 px-3 py-2 text-foreground">Approve</Button>);
    actions.push(
      <Button
        key="reject"
        onClick={() => {
          const reason = prompt("Enter rejection reason");
          if (reason) rejectClaim(data.id, reason);
        }}
        className="rounded-lg bg-red-600 px-3 py-2 text-foreground"
      >
        Reject
      </Button>
    );
  }
  if (data.status === "approved") {
    actions.push(
      <Button key="post" onClick={() => postClaim(data.id)} className="rounded-lg bg-indigo-600 px-3 py-2 text-foreground">
        Post to GL
      </Button>
    );
  }
  if (data.status === "posted") {
    actions.push(
      <Button
        key="reverse"
        onClick={() => {
          const reason = prompt("Enter reversal reason");
          if (reason) reverseClaim(data.id, reason);
        }}
        className="rounded-lg bg-amber-600 px-3 py-2 text-foreground"
      >
        Reverse
      </Button>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">
            {data.claim_number || `Draft #${data.id}`} <span className="text-sm text-gray-500">({data.status})</span>
          </h2>
          <p className="text-sm text-gray-500">
            Date: {formatDate(data.claim_date)} · Employee: {data.employee_id}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>

      <div className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex gap-4 text-sm text-gray-700">
          <span className="font-medium text-gray-900">Total:</span> {data.total_claimed_amount.toLocaleString()} {data.currency}
        </div>
        <div className="flex gap-4 text-sm text-gray-700">
          <span className="font-medium text-gray-900">Base:</span> {data.base_currency} @ {Number(data.conversion_rate).toFixed(4)}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Line</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Date</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Category</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Amount</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Funding</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Receipt</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.lines.map((line) => (
              <tr key={line.id}>
                <td className="px-4 py-2 text-sm text-gray-900">{line.description}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{formatDate(line.expense_date)}</td>
                <td className="px-4 py-2 text-sm text-gray-700">#{line.category_id}</td>
                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                  {line.claimed_amount.toLocaleString()} {line.currency}
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">{line.funding_method}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{line.has_receipt ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}