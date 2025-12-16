'use client';

import React from 'react';
import { useExpenseClaims } from '@/hooks/useExpenses';
import { formatDate } from '@/lib/utils';

export default function ExpenseClaimsPage() {
  const { data, error } = useExpenseClaims({ limit: 50 });

  if (error) return <div className="text-red-600">Failed to load claims</div>;
  if (!data) return <div>Loading claims...</div>;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Expense Claims</h2>
        <p className="text-sm text-gray-500">Recent claims with status and totals.</p>
      </div>
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Claim</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Date</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Amount</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Currency</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map((claim) => (
              <tr key={claim.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm text-gray-900">
                  {claim.claim_number || `Draft #${claim.id}`}<br />
                  <span className="text-xs text-gray-500">{claim.title}</span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">{formatDate(claim.claim_date)}</td>
                <td className="px-4 py-2">
                  <span className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                    {claim.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                  {claim.total_claimed_amount.toLocaleString()}
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">{claim.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
