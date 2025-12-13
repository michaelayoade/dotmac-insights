'use client';

import Link from 'next/link';
import { AlertTriangle, ArrowLeft, FileText, Layers } from 'lucide-react';
import { useAccountingTaxCategories, useAccountingTaxTemplates, useAccountingTaxPayable, useAccountingTaxReceivable } from '@/hooks/useApi';

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Layers className="w-4 h-4 text-teal-electric" />
        <div>
          <h3 className="text-white font-semibold">{title}</h3>
          {description && <p className="text-xs text-slate-muted">{description}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

function Table({
  columns,
  data,
  empty,
}: {
  columns: { key: string; title: string; align?: 'right' }[];
  data: any[];
  empty: string;
}) {
  if (!data?.length) {
    return <p className="text-slate-muted text-sm">{empty}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-slate-muted">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-2 py-2 text-left ${col.align === 'right' ? 'text-right' : ''}`}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx} className="border-t border-slate-border/60">
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-2 py-2 text-slate-100 ${col.align === 'right' ? 'text-right' : ''}`}
                >
                  {row[col.key] ?? '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AccountingTaxesPage() {
  const { data: categoriesData, error: categoriesError, isLoading: loadingCategories } = useAccountingTaxCategories();
  const { data: templatesData, error: templatesError, isLoading: loadingTemplates } = useAccountingTaxTemplates();
  const { data: payableData } = useAccountingTaxPayable();
  const { data: receivableData } = useAccountingTaxReceivable();

  const categories = categoriesData?.tax_categories || [];
  const salesTemplates = templatesData?.sales?.sales_tax_templates || [];
  const purchaseTemplates = templatesData?.purchase?.purchase_tax_templates || [];
  const itemTemplates = templatesData?.item?.item_tax_templates || [];
  const taxRules = templatesData?.rules?.tax_rules || [];
  const payableTotal = payableData?.total ?? 0;
  const receivableTotal = receivableData?.total ?? 0;

  const hasError = categoriesError || templatesError;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/books"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-slate-border text-sm text-slate-muted hover:text-white hover:border-slate-border/70"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Books
          </Link>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-slate-muted">Books</p>
            <h1 className="text-xl font-semibold text-white">Taxes & VAT</h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-slate-card border border-slate-border rounded-lg px-4 py-3">
            <p className="text-xs uppercase text-slate-muted tracking-[0.1em]">Tax Payable</p>
            <p className="text-lg font-semibold text-white">{payableTotal.toLocaleString()}</p>
          </div>
          <div className="bg-slate-card border border-slate-border rounded-lg px-4 py-3">
            <p className="text-xs uppercase text-slate-muted tracking-[0.1em]">Tax Receivable</p>
            <p className="text-lg font-semibold text-white">{receivableTotal.toLocaleString()}</p>
          </div>
        </div>
      </div>

      {hasError && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>Failed to load tax reference data</span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <SectionCard title="Tax Categories" description="Withholding and VAT categories">
          {loadingCategories ? (
            <p className="text-slate-muted text-sm">Loading...</p>
          ) : (
            <Table
              columns={[
                { key: 'name', title: 'Name' },
                { key: 'description', title: 'Description' },
                { key: 'rate', title: 'Rate', align: 'right' },
                { key: 'is_withholding', title: 'Withholding?' },
              ]}
              data={categories.map((c: any) => ({
                name: c.name ?? c.category ?? '-',
                description: c.description ?? '',
                rate: c.rate ?? c.tax_rate ?? '-',
                is_withholding: c.is_withholding ? 'Yes' : 'No',
              }))}
              empty="No tax categories found"
            />
          )}
        </SectionCard>

        <SectionCard title="Tax Rules" description="Applied overrides and rules">
          {loadingTemplates ? (
            <p className="text-slate-muted text-sm">Loading...</p>
          ) : (
            <Table
              columns={[
                { key: 'name', title: 'Name' },
                { key: 'type', title: 'Type' },
                { key: 'rate', title: 'Rate', align: 'right' },
              ]}
            data={taxRules.map((r: any) => ({
              name: r.name ?? r.rule ?? '-',
              type: r.type ?? r.rule_type ?? '-',
              rate: r.rate ?? r.tax_rate ?? '-',
            }))}
            empty="No tax rules found"
            />
          )}
        </SectionCard>
      </div>

      <SectionCard title="Sales Tax Templates" description="Sales VAT templates">
        {loadingTemplates ? (
          <p className="text-slate-muted text-sm">Loading...</p>
        ) : (
          <Table
            columns={[
              { key: 'name', title: 'Name' },
              { key: 'description', title: 'Description' },
              { key: 'rate', title: 'Rate', align: 'right' },
            ]}
            data={salesTemplates.map((t: any) => ({
              name: t.name ?? '-',
              description: t.description ?? '',
              rate: t.rate ?? t.tax_rate ?? '-',
            }))}
            empty="No sales tax templates found"
          />
        )}
      </SectionCard>

      <SectionCard title="Purchase Tax Templates" description="AP VAT templates">
        {loadingTemplates ? (
          <p className="text-slate-muted text-sm">Loading...</p>
        ) : (
          <Table
            columns={[
              { key: 'name', title: 'Name' },
              { key: 'description', title: 'Description' },
              { key: 'rate', title: 'Rate', align: 'right' },
            ]}
            data={purchaseTemplates.map((t: any) => ({
              name: t.name ?? '-',
              description: t.description ?? '',
              rate: t.rate ?? t.tax_rate ?? '-',
            }))}
            empty="No purchase tax templates found"
          />
        )}
      </SectionCard>

      <SectionCard title="Item Tax Templates" description="Item-level tax templates">
        {loadingTemplates ? (
          <p className="text-slate-muted text-sm">Loading...</p>
        ) : (
          <Table
            columns={[
              { key: 'name', title: 'Name' },
              { key: 'description', title: 'Description' },
              { key: 'rate', title: 'Rate', align: 'right' },
            ]}
            data={itemTemplates.map((t: any) => ({
              name: t.name ?? '-',
              description: t.description ?? '',
              rate: t.rate ?? t.tax_rate ?? '-',
            }))}
            empty="No item tax templates found"
          />
        )}
      </SectionCard>
    </div>
  );
}
