"use client";

import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  MapPin,
  Calendar,
  TrendingDown,
  User,
  Package,
  Shield,
  FileWarning,
  Wrench,
  CheckCircle,
  Trash2,
  RefreshCw,
  Edit,
} from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { formatStatusLabel, type StatusTone } from "@/lib/status-pill";
import { useAsset, useAssetMutations } from "@/hooks/useApi";
import type { AssetDetail } from "@/lib/api";
import { Button, StatusPill } from '@/components/ui';

const STATUS_TONES: Record<string, StatusTone> = {
  draft: "default",
  submitted: "info",
  partially_depreciated: "warning",
  fully_depreciated: "success",
  sold: "info",
  scrapped: "danger",
  in_maintenance: "warning",
  out_of_order: "danger",
};

function InfoCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-indigo-300" />
        <h3 className="font-semibold text-foreground">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-slate-border last:border-0">
      <span className="text-sm text-slate-muted">{label}</span>
      <span className="text-sm text-foreground text-right">{value ?? "-"}</span>
    </div>
  );
}

export default function AssetDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const assetId = parseInt(resolvedParams.id, 10);

  const { data: assetData, isLoading, mutate } = useAsset(assetId);
  const asset = assetData as AssetDetail | undefined;
  const { submitAsset, scrapAsset, markForMaintenance, completeMaintenance } = useAssetMutations();

  const handleSubmit = async () => {
    try {
      await submitAsset(assetId);
      mutate();
    } catch (error) {
      console.error("Failed to submit asset:", error);
    }
  };

  const handleScrap = async () => {
    if (!confirm("Are you sure you want to scrap this asset? This action cannot be undone.")) return;
    try {
      await scrapAsset(assetId);
      mutate();
    } catch (error) {
      console.error("Failed to scrap asset:", error);
    }
  };

  const handleMarkMaintenance = async () => {
    try {
      await markForMaintenance(assetId);
      mutate();
    } catch (error) {
      console.error("Failed to mark for maintenance:", error);
    }
  };

  const handleCompleteMaintenance = async () => {
    try {
      await completeMaintenance(assetId);
      mutate();
    } catch (error) {
      console.error("Failed to complete maintenance:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-6 h-6 animate-spin text-slate-muted" />
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="text-center py-12">
        <Building2 className="w-8 h-8 mx-auto mb-3 text-slate-muted opacity-50" />
        <p className="text-slate-muted">Asset not found</p>
        <Link href="/assets/list" className="text-indigo-400 hover:text-indigo-300 text-sm mt-2 inline-block">
          Back to Assets
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/assets/list"
            className="p-2 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{asset.asset_name}</h1>
              <StatusPill
                label={formatStatusLabel(asset.status)}
                tone={STATUS_TONES[asset.status ?? "draft"] || "default"}
                size="md"
              />
            </div>
            {asset.item_code && (
              <p className="text-sm text-slate-muted mt-1">Item: {asset.item_code}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {asset.status === "draft" && (
            <Button
              onClick={handleSubmit}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm text-foreground transition-colors"
            >
              <CheckCircle className="w-4 h-4" />
              Submit
            </Button>
          )}
          {asset.status === "in_maintenance" && (
            <Button
              onClick={handleCompleteMaintenance}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm text-foreground transition-colors"
            >
              <CheckCircle className="w-4 h-4" />
              Complete Maintenance
            </Button>
          )}
          {asset.status && ["submitted", "partially_depreciated"].includes(asset.status) && (
            <>
              <Button
                onClick={handleMarkMaintenance}
                className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 rounded-lg text-sm text-foreground transition-colors"
              >
                <Wrench className="w-4 h-4" />
                Mark for Maintenance
              </Button>
              <Button
                onClick={handleScrap}
                className="flex items-center gap-2 px-4 py-2 bg-coral-alert hover:bg-red-600 rounded-lg text-sm text-foreground transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Scrap
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Basic Info */}
        <InfoCard title="Basic Information" icon={Building2}>
          <InfoRow label="Asset Name" value={asset.asset_name} />
          <InfoRow label="Category" value={asset.asset_category} />
          <InfoRow label="Item Code" value={asset.item_code} />
          <InfoRow label="Item Name" value={asset.item_name} />
          <InfoRow label="Serial No" value={asset.serial_no} />
          <InfoRow label="Quantity" value={asset.asset_quantity} />
        </InfoCard>

        {/* Location */}
        <InfoCard title="Location & Assignment" icon={MapPin}>
          <InfoRow label="Company" value={asset.company} />
          <InfoRow label="Location" value={asset.location} />
          <InfoRow label="Department" value={asset.department} />
          <InfoRow label="Cost Center" value={asset.cost_center} />
          <InfoRow label="Custodian" value={asset.custodian} />
          <InfoRow label="Asset Owner" value={asset.asset_owner} />
        </InfoCard>

        {/* Purchase Info */}
        <InfoCard title="Purchase Details" icon={Calendar}>
          <InfoRow label="Purchase Date" value={asset.purchase_date ? formatDate(asset.purchase_date) : null} />
          <InfoRow label="Available for Use" value={asset.available_for_use_date ? formatDate(asset.available_for_use_date) : null} />
          <InfoRow label="Gross Purchase Amount" value={formatCurrency(asset.gross_purchase_amount ?? 0)} />
          <InfoRow label="Supplier" value={asset.supplier} />
          <InfoRow label="Purchase Receipt" value={asset.purchase_receipt} />
          <InfoRow label="Purchase Invoice" value={asset.purchase_invoice} />
        </InfoCard>

        {/* Valuation */}
        <InfoCard title="Valuation" icon={TrendingDown}>
          <InfoRow label="Asset Value (Book)" value={formatCurrency(asset.asset_value ?? 0)} />
          <InfoRow label="Opening Accumulated Depreciation" value={formatCurrency(asset.opening_accumulated_depreciation ?? 0)} />
          <InfoRow label="Calculate Depreciation" value={asset.calculate_depreciation ? "Yes" : "No"} />
          <InfoRow label="Is Existing Asset" value={asset.is_existing_asset ? "Yes" : "No"} />
          <InfoRow label="Is Composite Asset" value={asset.is_composite_asset ? "Yes" : "No"} />
          <InfoRow label="Next Depreciation Date" value={asset.next_depreciation_date ? formatDate(asset.next_depreciation_date) : null} />
        </InfoCard>

        {/* Warranty */}
        <InfoCard title="Warranty" icon={Shield}>
          <InfoRow label="Warranty Expiry" value={asset.warranty_expiry_date ? formatDate(asset.warranty_expiry_date) : null} />
          <InfoRow label="Maintenance Required" value={asset.maintenance_required ? "Yes" : "No"} />
        </InfoCard>

        {/* Insurance */}
        <InfoCard title="Insurance" icon={FileWarning}>
          <InfoRow label="Insured Value" value={formatCurrency(asset.insured_value ?? 0)} />
          <InfoRow label="Insurance Start" value={asset.insurance_start_date ? formatDate(asset.insurance_start_date) : null} />
          <InfoRow label="Insurance End" value={asset.insurance_end_date ? formatDate(asset.insurance_end_date) : null} />
          <InfoRow label="Comprehensive Insurance" value={asset.comprehensive_insurance} />
        </InfoCard>
      </div>

      {/* Finance Books */}
      {asset.finance_books && asset.finance_books.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Finance Books</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-border">
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Book</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Method</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Depreciations</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Frequency</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Rate</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Value After Dep</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {asset.finance_books.map((book, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2 text-sm text-foreground">{book.finance_book || "Default"}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted capitalize">{book.depreciation_method || "-"}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted text-right">{book.total_number_of_depreciations}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted text-right">{book.frequency_of_depreciation} mo</td>
                    <td className="px-4 py-2 text-sm text-slate-muted text-right">{book.rate_of_depreciation}%</td>
                    <td className="px-4 py-2 text-sm text-foreground text-right">{formatCurrency(book.value_after_depreciation ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Depreciation Schedule */}
      {asset.depreciation_schedules && asset.depreciation_schedules.length > 0 && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Depreciation Schedule</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-border">
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Date</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Finance Book</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Depreciation</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-slate-muted uppercase">Accumulated</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Journal Entry</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-slate-muted uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-border">
                {asset.depreciation_schedules.slice(0, 12).map((entry, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2 text-sm text-foreground">{formatDate(entry.schedule_date)}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted">{entry.finance_book || "Default"}</td>
                    <td className="px-4 py-2 text-sm text-foreground text-right">{formatCurrency(entry.depreciation_amount)}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted text-right">{formatCurrency(entry.accumulated_depreciation_amount)}</td>
                    <td className="px-4 py-2 text-sm text-slate-muted">{entry.journal_entry || "-"}</td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          "px-2 py-1 text-xs font-medium rounded-full",
                          entry.depreciation_booked
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-slate-500/20 text-slate-400"
                        )}
                      >
                        {entry.depreciation_booked ? "Booked" : "Pending"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {asset.depreciation_schedules.length > 12 && (
              <p className="text-sm text-slate-muted text-center py-3 border-t border-slate-border">
                Showing 12 of {asset.depreciation_schedules.length} entries
              </p>
            )}
          </div>
        </div>
      )}

      {/* Description */}
      {asset.description && (
        <div className="bg-slate-card border border-slate-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-3">Description</h3>
          <p className="text-sm text-slate-muted whitespace-pre-wrap">{asset.description}</p>
        </div>
      )}
    </div>
  );
}
