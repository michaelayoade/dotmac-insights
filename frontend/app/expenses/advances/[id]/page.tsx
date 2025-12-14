"use client";

import { useParams } from "next/navigation";
import dayjs from "dayjs";
import { useCashAdvanceDetail, useCashAdvanceMutations } from "@/hooks/useExpenses";

export default function CashAdvanceDetailPage() {
  const params = useParams<{ id: string }>();
  const advanceId = Number(params?.id);
  const { data, error } = useCashAdvanceDetail(advanceId);
  const { submitAdvance, approveAdvance, rejectAdvance, disburseAdvance, settleAdvance } = useCashAdvanceMutations();

  if (error) return <div className="text-red-600">Failed to load cash advance</div>;
  if (!data) return <div>Loading cash advance...</div>;

  const actions = [];
  if (data.status === "draft") {
    actions.push(<button key="submit" onClick={() => submitAdvance(data.id)} className="rounded-lg bg-blue-600 px-3 py-2 text-white">Submit</button>);
  }
  if (data.status === "pending_approval") {
    actions.push(<button key="approve" onClick={() => approveAdvance(data.id)} className="rounded-lg bg-green-600 px-3 py-2 text-white">Approve</button>);
    actions.push(
      <button
        key="reject"
        onClick={() => {
          const reason = prompt("Enter rejection reason");
          if (reason) rejectAdvance(data.id, reason);
        }}
        className="rounded-lg bg-red-600 px-3 py-2 text-white"
      >
        Reject
      </button>
    );
  }
  if (data.status === "approved" || data.status === "pending_approval") {
    actions.push(
      <button
        key="disburse"
        onClick={() => {
          const amountStr = prompt("Disburse amount", String(data.requested_amount));
          if (!amountStr) return;
          const amount = Number(amountStr);
          disburseAdvance(data.id, { amount });
        }}
        className="rounded-lg bg-indigo-600 px-3 py-2 text-white"
      >
        Disburse
      </button>
    );
  }
  if (data.status === "disbursed" || data.status === "partially_settled") {
    actions.push(
      <button
        key="settle"
        onClick={() => {
          const amountStr = prompt("Settle amount", "0");
          const refundStr = prompt("Refund amount (if any)", "0");
          if (amountStr === null || refundStr === null) return;
          settleAdvance(data.id, { amount: Number(amountStr), refund_amount: Number(refundStr) });
        }}
        className="rounded-lg bg-amber-600 px-3 py-2 text-white"
      >
        Settle
      </button>
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
            Request Date: {dayjs(data.request_date).format("YYYY-MM-DD")} · Employee: {data.employee_id}
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
