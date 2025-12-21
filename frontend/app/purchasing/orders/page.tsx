'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchasingOrders, usePurchasingSuppliers } from '@/hooks/useApi';
import { DataTable, Pagination } from '@/components/DataTable';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  ShoppingCart,
  Calendar,
  DollarSign,
  Building2,
  CheckCircle2,
  Clock,
  XCircle,
  Filter,
  Search,
  FileText,
  Package,
  Send,
  Truck,
} from 'lucide-react';

function formatCurrency(value: number | undefined | null, currency = 'NGN'): string {
  if (value === undefined || value === null) return '₦0';
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0';
  return new Intl.NumberFormat('en-NG').format(value);
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

export default function PurchasingOrdersPage() {
  const router = useRouter();
  const currency = 'NGN';
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [supplierId, setSupplierId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const { data, isLoading, error } = usePurchasingOrders({
    status: status || undefined,
    supplier: supplierId || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    search: search || undefined,
    currency,
    limit: pageSize,
    offset: (page - 1) * pageSize,
  });

  const { data: suppliersData } = usePurchasingSuppliers({ limit: 100, offset: 0 });

  const orders = data?.orders || [];
  const total = data?.total || 0;
  const suppliers = suppliersData?.suppliers || [];
  const totalValue = orders.reduce((sum: number, o: any) => sum + (o.total || 0), 0);

  const getStatusConfig = (orderStatus: string) => {
    const statusLower = orderStatus?.toLowerCase() || '';
    const configs: Record<string, { color: string; icon: typeof CheckCircle2; label: string }> = {
      draft: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: FileText,
        label: 'Draft',
      },
      pending: {
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock,
        label: 'Pending',
      },
      approved: {
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: CheckCircle2,
        label: 'Approved',
      },
      sent: {
        color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
        icon: Send,
        label: 'Sent',
      },
      received: {
        color: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
        icon: Package,
        label: 'Received',
      },
      partially_received: {
        color: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
        icon: Truck,
        label: 'Partial',
      },
      completed: {
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2,
        label: 'Completed',
      },
      cancelled: {
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: XCircle,
        label: 'Cancelled',
      },
      closed: {
        color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
        icon: XCircle,
        label: 'Closed',
      },
    };
    return configs[statusLower] || configs.draft;
  };

  const columns = [
    {
      key: 'order_number',
      header: 'PO #',
      sortable: true,
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <ShoppingCart className="w-4 h-4 text-teal-electric" />
          <span className="font-mono text-foreground font-medium">
            {item.order_no || item.order_number || item.po_number || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'supplier',
      header: 'Supplier',
      render: (item: any) => (
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-muted" />
          <span className="text-foreground-secondary truncate max-w-[180px]">
            {item.supplier || '-'}
          </span>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Order Date',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Calendar className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">
            {formatDate(item.date)}
          </span>
        </div>
      ),
    },
    {
      key: 'delivery_date',
      header: 'Expected Delivery',
      render: (item: any) => (
        <div className="flex items-center gap-1 text-sm">
          <Truck className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground-secondary">
            {formatDate(item.delivery_date || item.expected_delivery_date)}
          </span>
        </div>
      ),
    },
    {
      key: 'items',
      header: 'Items',
      align: 'center' as const,
      render: (item: any) => (
        <div className="flex items-center justify-center gap-1">
          <Package className="w-3 h-3 text-slate-muted" />
          <span className="text-foreground">{formatNumber(item.item_count || item.line_items?.length || 0)}</span>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (item: any) => (
        <span className="font-mono text-foreground font-medium">
          {formatCurrency(item.total)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load purchase orders</p>
          <p className="text-slate-muted text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Purchase Orders</h1>
          <p className="text-slate-muted text-sm">Create and track purchase orders with write-back status</p>
        </div>
        <button
          onClick={() => router.push('/purchasing/orders/new')}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90"
        >
          <ShoppingCart className="w-4 h-4" />
          New Purchase Order
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <ShoppingCart className="w-4 h-4 text-teal-electric" />
            <p className="text-slate-muted text-sm">Total Orders</p>
          </div>
          <p className="text-2xl font-bold text-foreground">{formatNumber(total)}</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-blue-400" />
            <p className="text-blue-400 text-sm">Total Value</p>
          </div>
          <p className="text-xl font-bold text-blue-400">
            {formatCurrency(totalValue)}
          </p>
        </div>
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-yellow-400" />
            <p className="text-yellow-400 text-sm">Pending</p>
          </div>
          <p className="text-xl font-bold text-yellow-400">
            {formatNumber(0)}
          </p>
          <p className="text-xs text-yellow-400/70">
            {formatCurrency(0)} value
          </p>
        </div>
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <p className="text-green-400 text-sm">This Month</p>
          </div>
          <p className="text-xl font-bold text-green-400">
            {formatNumber(0)}
          </p>
          <p className="text-xs text-green-400/70">
            {formatCurrency(0)} value
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-teal-electric" />
          <span className="text-foreground text-sm font-medium">Filters</span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px] max-w-md relative">
            <Search className="w-4 h-4 text-slate-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search orders..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-elevated border border-slate-border rounded-lg pl-10 pr-4 py-2 text-sm text-foreground placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            />
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
          >
            <option value="">All Status</option>
            <option value="draft">Draft</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="sent">Sent</option>
            <option value="partially_received">Partially Received</option>
            <option value="received">Received</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          {suppliers.length > 0 && (
            <select
              value={supplierId}
              onChange={(e) => {
                setSupplierId(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50 max-w-[200px]"
            >
              <option value="">All Suppliers</option>
              {suppliers.map((supplier: any) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name || supplier.supplier_name}
                </option>
              ))}
            </select>
          )}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="Start date"
            />
            <span className="text-slate-muted">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
              placeholder="End date"
            />
          </div>
          {(search || status || supplierId || startDate || endDate) && (
            <button
              onClick={() => {
                setSearch('');
                setStatus('');
                setSupplierId('');
                setStartDate('');
                setEndDate('');
                setPage(1);
              }}
              className="text-slate-muted text-sm hover:text-foreground transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={orders}
        keyField="id"
        loading={isLoading}
        emptyMessage="No purchase orders found"
        onRowClick={(item) => router.push(`/purchasing/orders/${(item as any).id}`)}
        className="cursor-pointer"
      />

      {/* Pagination */}
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
