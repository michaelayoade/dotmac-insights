import React from 'react';
import dayjs from 'dayjs';
import { useCashAdvances } from '@/hooks/useExpenses';

export default function CashAdvancesPage() {
  const { data, error } = useCashAdvances({ limit: 50 });

  if (error) return <div className="text-red-600">Failed to load cash advances</div>;
  if (!data) return <div>Loading cash advances...</div>;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Cash Advances</h2>
        <p className="text-sm text-gray-500">Track requests, disbursements, and settlements.</p>
      </div>
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Advance</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Request Date</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Requested</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Disbursed</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Outstanding</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map((advance) => (
              <tr key={advance.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm text-gray-900">
                  {advance.advance_number || `Draft #${advance.id}`}<br />
                  <span className="text-xs text-gray-500">{advance.purpose}</span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">
                  {dayjs(advance.request_date).format('YYYY-MM-DD')}
                </td>
                <td className="px-4 py-2">
                  <span className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                    {advance.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                  {advance.requested_amount.toLocaleString()} {advance.currency}
                </td>
                <td className="px-4 py-2 text-sm text-gray-900">
                  {advance.disbursed_amount.toLocaleString()} {advance.currency}
                </td>
                <td className="px-4 py-2 text-sm text-gray-900">
                  {advance.outstanding_amount.toLocaleString()} {advance.currency}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
