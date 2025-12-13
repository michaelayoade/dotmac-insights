'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useFinanceOrders } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { AlertTriangle, ShoppingCart, FileText } from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function SalesOrdersPage() {
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const { data, isLoading, error } = useFinanceOrders({
    currency,
    page,
    page_size: pageSize,
    sort_by: 'order_date',
    sort_order: 'desc',
  });

  const orders = data?.orders || [];
  const total = data?.total || 0;

  const columns = [
    {
      key: 'order_number',
      header: 'Order #',
      render: (item: any) => (
        <span className="font-mono text-white">{item.order_number || `#${item.id}`}</span>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (item: any) => (
        <span className="text-slate-200">{item.customer_name || `Customer ${item.customer_id || ''}`}</span>
      ),
    },
    {
      key: 'order_date',
      header: 'Order Date',
      render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.transaction_date || item.order_date)}</span>,
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-white">{formatCurrency(item.total_amount || 0, item.currency || currency)}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: any) => (
        <span className="text-xs text-slate-muted capitalize">{item.status || 'draft'}</span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-400">Failed to load orders</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingCart className="w-5 h-5 text-teal-electric" />
          <h1 className="text-xl font-semibold text-white">Sales Orders</h1>
        </div>
        <Link
          href="/sales/orders/new"
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-teal-electric/50 text-sm text-teal-electric hover:text-teal-glow hover:border-teal-electric/70"
        >
          <FileText className="w-4 h-4" />
          New Order
        </Link>
      </div>

      <DataTable
        columns={columns}
        data={orders}
        keyField="id"
        loading={isLoading}
        emptyMessage="No orders found"
        onRowClick={(item) => router.push(`/sales/orders/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {total > pageSize && (
        <Pagination
          total={total}
          limit={pageSize}
          offset={(page - 1) * pageSize}
          onPageChange={(newOffset) => setPage(Math.floor(newOffset / pageSize) + 1)}
          onLimitChange={(newLimit) => {
            setPageSize(newLimit);
            setPage(1);
          }}
        />
      )}
    </div>
  );
}
