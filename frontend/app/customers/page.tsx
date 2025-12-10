'use client';

import { useState } from 'react';
import { Search, Filter, User, Mail, Phone, Calendar, AlertCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/Card';
import { Badge, StatusBadge } from '@/components/Badge';
import { DataTable, Pagination } from '@/components/DataTable';
import { useCustomers, useCustomer } from '@/hooks/useApi';
import { formatCurrency, formatDate, formatNumber, cn, debounce } from '@/lib/utils';
import { Select } from '@dotmac/core';

export default function CustomersPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [billingTypeFilter, setBillingTypeFilter] = useState<string>('');
  const [offset, setOffset] = useState(0);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const limit = 20;

  const { data, isLoading } = useCustomers({
    search: search || undefined,
    status: statusFilter || undefined,
    customer_type: typeFilter || undefined,
    billing_type: billingTypeFilter || undefined,
    limit,
    offset,
  });

  const { data: selectedCustomer } = useCustomer(selectedCustomerId);

  const handleSearchChange = debounce((value: string) => {
    setSearch(value);
    setOffset(0);
  }, 300);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-3xl font-bold text-white">Customers</h1>
        <p className="text-slate-muted mt-1">
          Manage and analyze your customer base
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main Content */}
        <div className="flex-1 space-y-4">
          {/* Filters */}
          <Card padding="sm">
            <div className="flex flex-col md:flex-row gap-4">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted" />
                <input
                  type="text"
                  placeholder="Search by name, email, phone..."
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-white placeholder-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50 focus:border-teal-electric/50 transition-colors"
                />
              </div>

              {/* Status Filter */}
              <Select
                placeholder="All Status"
                value={statusFilter}
                onValueChange={(value) => {
                  setStatusFilter(value);
                  setOffset(0);
                }}
                options={[
                  { value: '', label: 'All Status' },
                  { value: 'active', label: 'Active' },
                  { value: 'inactive', label: 'Inactive' },
                  { value: 'suspended', label: 'Suspended' },
                  { value: 'cancelled', label: 'Cancelled' },
                ]}
                size="sm"
                className="w-[140px]"
              />

              {/* Type Filter */}
              <Select
                placeholder="All Types"
                value={typeFilter}
                onValueChange={(value) => {
                  setTypeFilter(value);
                  setOffset(0);
                }}
                options={[
                  { value: '', label: 'All Types' },
                  { value: 'residential', label: 'Residential' },
                  { value: 'business', label: 'Business' },
                  { value: 'enterprise', label: 'Enterprise' },
                ]}
                size="sm"
                className="w-[140px]"
              />

              {/* Billing Type Filter */}
              <Select
                placeholder="All Billing"
                value={billingTypeFilter}
                onValueChange={(value) => {
                  setBillingTypeFilter(value);
                  setOffset(0);
                }}
                options={[
                  { value: '', label: 'All Billing' },
                  { value: 'prepaid', label: 'Prepaid' },
                  { value: 'prepaid_monthly', label: 'Prepaid Monthly' },
                  { value: 'recurring', label: 'Recurring' },
                ]}
                size="sm"
                className="w-[160px]"
              />
            </div>
          </Card>

          {/* Results count */}
          {data && (
            <div className="flex items-center justify-between">
              <p className="text-slate-muted text-sm">
                {data.total.toLocaleString()} customer{data.total !== 1 ? 's' : ''} found
              </p>
            </div>
          )}

          {/* Customer Table */}
          <Card padding="none">
            <DataTable
              columns={[
                {
                  key: 'name',
                  header: 'Customer',
                  render: (item) => (
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-slate-elevated flex items-center justify-center text-teal-electric font-medium font-mono text-sm">
                        {(item.name as string).charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-white font-medium font-body">{item.name as string}</p>
                        <p className="text-slate-muted text-xs">{String(item.account_number || '—')}</p>
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'email',
                  header: 'Contact',
                  render: (item) => (
                    <div className="space-y-0.5">
                      {item.email ? (
                        <p className="text-slate-muted text-sm">{item.email as string}</p>
                      ) : null}
                      {item.phone ? (
                        <p className="text-slate-muted text-sm">{item.phone as string}</p>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (item) => <StatusBadge status={item.status as string} />,
                },
                {
                  key: 'customer_type',
                  header: 'Type',
                  render: (item) => (
                    <span className="text-slate-muted capitalize">{item.customer_type as string}</span>
                  ),
                },
                {
                  key: 'billing_type',
                  header: 'Billing',
                  render: (item) => (
                    <span className="text-slate-muted capitalize">
                      {item.billing_type ? (item.billing_type as string).replace('_', ' ') : '—'}
                    </span>
                  ),
                },
                {
                  key: 'tenure_days',
                  header: 'Tenure',
                  align: 'right',
                  render: (item) => {
                    const days = item.tenure_days as number;
                    if (days < 30) return `${days}d`;
                    if (days < 365) return `${Math.floor(days / 30)}mo`;
                    return `${Math.floor(days / 365)}y ${Math.floor((days % 365) / 30)}mo`;
                  },
                },
              ]}
              data={(data?.data || []) as unknown as Record<string, unknown>[]}
              keyField="id"
              loading={isLoading}
              emptyMessage="No customers found"
              onRowClick={(item) => setSelectedCustomerId(item.id as number)}
            />
            {data && data.total > limit && (
              <Pagination
                total={data.total}
                limit={limit}
                offset={offset}
                onPageChange={setOffset}
              />
            )}
          </Card>
        </div>

        {/* Customer Detail Sidebar */}
        {selectedCustomer && (
          <div className="lg:w-96">
            <Card className="sticky top-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display font-semibold text-white">Customer Details</h3>
                <button
                  onClick={() => setSelectedCustomerId(null)}
                  className="text-slate-muted hover:text-white transition-colors"
                >
                  ×
                </button>
              </div>

              {/* Customer Header */}
              <div className="flex items-start gap-4 mb-6 pb-6 border-b border-slate-border">
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-teal-electric to-teal-glow flex items-center justify-center text-slate-deep font-bold text-xl">
                  {selectedCustomer.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-white font-semibold truncate">{selectedCustomer.name}</h4>
                  <p className="text-slate-muted text-sm">{selectedCustomer.account_number || 'No account #'}</p>
                  <div className="mt-2">
                    <StatusBadge status={selectedCustomer.status} />
                  </div>
                </div>
              </div>

              {/* Contact Info */}
              <div className="space-y-3 mb-6">
                {selectedCustomer.email && (
                  <div className="flex items-center gap-3 text-sm">
                    <Mail className="w-4 h-4 text-slate-muted" />
                    <span className="text-white">{selectedCustomer.email}</span>
                  </div>
                )}
                {selectedCustomer.phone && (
                  <div className="flex items-center gap-3 text-sm">
                    <Phone className="w-4 h-4 text-slate-muted" />
                    <span className="text-white">{selectedCustomer.phone}</span>
                  </div>
                )}
                {selectedCustomer.signup_date && (
                  <div className="flex items-center gap-3 text-sm">
                    <Calendar className="w-4 h-4 text-slate-muted" />
                    <span className="text-slate-muted">
                      Customer since {formatDate(selectedCustomer.signup_date)}
                    </span>
                  </div>
                )}
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                <div className="bg-slate-elevated rounded-lg p-3">
                  <p className="text-slate-muted text-xs uppercase">Total Invoiced</p>
                  <p className="font-mono font-semibold text-white mt-1">
                    {formatCurrency(selectedCustomer.metrics.total_invoiced)}
                  </p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-3">
                  <p className="text-slate-muted text-xs uppercase">Outstanding</p>
                  <p className={cn(
                    'font-mono font-semibold mt-1',
                    selectedCustomer.metrics.outstanding > 0 ? 'text-coral-alert' : 'text-teal-electric'
                  )}>
                    {formatCurrency(selectedCustomer.metrics.outstanding)}
                  </p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-3">
                  <p className="text-slate-muted text-xs uppercase">Open Tickets</p>
                  <p className={cn(
                    'font-mono font-semibold mt-1',
                    selectedCustomer.metrics.open_tickets > 0 ? 'text-amber-warn' : 'text-white'
                  )}>
                    {selectedCustomer.metrics.open_tickets}
                  </p>
                </div>
                <div className="bg-slate-elevated rounded-lg p-3">
                  <p className="text-slate-muted text-xs uppercase">Total Chats</p>
                  <p className="font-mono font-semibold text-white mt-1">
                    {selectedCustomer.metrics.total_conversations}
                  </p>
                </div>
              </div>

              {/* Active Subscriptions */}
              {selectedCustomer.subscriptions.length > 0 && (
                <div className="mb-6">
                  <h5 className="text-slate-muted text-xs uppercase tracking-wide mb-3">
                    Subscriptions
                  </h5>
                  <div className="space-y-2">
                    {selectedCustomer.subscriptions.map((sub) => (
                      <div
                        key={sub.id}
                        className="flex items-center justify-between py-2 px-3 bg-slate-elevated rounded-lg"
                      >
                        <div>
                          <p className="text-white text-sm font-medium">{sub.plan_name}</p>
                          {sub.download_speed && (
                            <p className="text-slate-muted text-xs">
                              {sub.download_speed}/{sub.upload_speed} Mbps
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className="text-teal-electric font-mono text-sm">
                            {formatCurrency(sub.price)}
                          </p>
                          <StatusBadge status={sub.status} size="sm" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Invoices */}
              {selectedCustomer.recent_invoices.length > 0 && (
                <div>
                  <h5 className="text-slate-muted text-xs uppercase tracking-wide mb-3">
                    Recent Invoices
                  </h5>
                  <div className="space-y-2">
                    {selectedCustomer.recent_invoices.slice(0, 5).map((inv) => (
                      <div
                        key={inv.id}
                        className="flex items-center justify-between py-2 border-b border-slate-border last:border-0"
                      >
                        <div>
                          <p className="text-white text-sm font-mono">
                            {inv.invoice_number || `#${inv.id}`}
                          </p>
                          <p className="text-slate-muted text-xs">
                            {formatDate(inv.invoice_date)}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-sm text-white">
                            {formatCurrency(inv.total_amount)}
                          </p>
                          <StatusBadge status={inv.status} size="sm" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
