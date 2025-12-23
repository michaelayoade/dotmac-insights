'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Car,
  Edit,
  Save,
  X,
  Shield,
  Calendar,
  MapPin,
  Fuel,
  Gauge,
  DollarSign,
  Users,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Palette,
  Hash,
  Building2,
  FileText,
  Clock,
} from 'lucide-react';
import { useFleetVehicle, useFleetMutations } from '@/hooks/useApi';
import { ErrorDisplay, LoadingState } from '@/components/insights/shared';
import { cn } from '@/lib/utils';
import { formatCurrency, formatNumber, formatDate } from '@/lib/formatters';
import { BackButton, Button } from '@/components/ui';

function daysUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = date.getTime() - today.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

interface InfoRowProps {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  iconColor?: string;
}

function InfoRow({ icon: Icon, label, value, iconColor = 'text-slate-muted' }: InfoRowProps) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-slate-border last:border-b-0">
      <Icon className={cn('w-5 h-5 mt-0.5', iconColor)} />
      <div className="flex-1">
        <p className="text-sm text-slate-muted">{label}</p>
        <div className="text-foreground">{value}</div>
      </div>
    </div>
  );
}

export default function VehicleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const isLicensePlateValid = Boolean(editForm.license_plate?.trim());

  const { data: vehicle, isLoading, error, mutate } = useFleetVehicle(id);
  const mutations = useFleetMutations();

  const startEditing = () => {
    if (!vehicle) return;
    setFormError(null);
    setEditForm({
      license_plate: vehicle.license_plate || '',
      make: vehicle.make || '',
      model: vehicle.model || '',
      model_year: vehicle.model_year ?? '',
      color: vehicle.color || '',
      odometer_value: vehicle.odometer_value || 0,
      acquisition_date: vehicle.acquisition_date || '',
      fuel_uom: vehicle.fuel_uom || '',
      location: vehicle.location || '',
      company: vehicle.company || '',
      is_active: vehicle.is_active,
      insurance_company: vehicle.insurance_company || '',
      policy_no: vehicle.policy_no || '',
      insurance_start_date: vehicle.insurance_start_date || '',
      insurance_end_date: vehicle.insurance_end_date || '',
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditForm({});
    setFormError(null);
  };

  const handleSave = async () => {
    if (!vehicle) return;
    setSaving(true);
    setFormError(null);
    try {
      // Build payload with only changed fields, converting empty strings to null for optional fields
      const payload: Record<string, any> = {};

      const licensePlate = editForm.license_plate?.trim() || '';
      if (!licensePlate) {
        setFormError('License plate is required.');
        return;
      }
      if (licensePlate !== vehicle.license_plate) {
        payload.license_plate = licensePlate;
      }

      // String fields - convert empty to null for optional fields
      const stringFields = ['make', 'model', 'color', 'location', 'fuel_uom', 'company', 'insurance_company', 'policy_no'];
      for (const field of stringFields) {
        const newVal = editForm[field]?.trim() || null;
        const oldVal = (vehicle as any)[field] || null;
        if (newVal !== oldVal) {
          payload[field] = newVal;
        }
      }

      // Date fields - convert empty to null
      const dateFields = ['acquisition_date', 'insurance_start_date', 'insurance_end_date'];
      for (const field of dateFields) {
        const newVal = editForm[field] || null;
        const oldVal = (vehicle as any)[field] || null;
        if (newVal !== oldVal) {
          payload[field] = newVal;
        }
      }

      // Odometer - only include if actually changed and is a valid number
      const newOdometer = editForm.odometer_value;
      if (typeof newOdometer === 'number' && !isNaN(newOdometer) && newOdometer !== vehicle.odometer_value) {
        payload.odometer_value = newOdometer;
      }

      // Model year - allow clearing
      const newModelYear = editForm.model_year;
      if (newModelYear === '' || newModelYear === null || newModelYear === undefined) {
        if (vehicle.model_year !== null && vehicle.model_year !== undefined) {
          payload.model_year = null;
        }
      } else if (!isNaN(Number(newModelYear)) && Number(newModelYear) !== vehicle.model_year) {
        payload.model_year = Number(newModelYear);
      }

      // Boolean field
      if (editForm.is_active !== vehicle.is_active) {
        payload.is_active = editForm.is_active;
      }

      // Only call API if there are changes
      if (Object.keys(payload).length > 0) {
        await mutations.updateVehicle(vehicle.id, payload);
        await mutate();
      }
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to update vehicle:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleFormChange = (field: string, value: any) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  if (isLoading) {
    return <LoadingState />;
  }

  if (!vehicle) {
    return (
      <div className="space-y-6">
        {error && (
          <ErrorDisplay
            message="Failed to load vehicle"
            error={error as Error}
            onRetry={() => mutate()}
          />
        )}
        <div className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="w-12 h-12 text-slate-muted mb-4" />
          <p className="text-foreground text-lg">Vehicle not found</p>
          <Link href="/fleet" className="mt-4 text-amber-400 hover:text-amber-300">
            Back to fleet
          </Link>
        </div>
      </div>
    );
  }

  const insuranceDays = daysUntil(vehicle.insurance_end_date);
  const insuranceExpiring = insuranceDays !== null && insuranceDays <= 30 && insuranceDays >= 0;
  const insuranceExpired = insuranceDays !== null && insuranceDays < 0;

  return (
    <div className="space-y-6">
      {error && (
        <ErrorDisplay
          message="Failed to load vehicle"
          error={error as Error}
          onRetry={() => mutate()}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <BackButton href="/fleet" label="fleet" />
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <Car className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-foreground">{vehicle.license_plate}</h1>
                <span className={cn(
                  'px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1',
                  vehicle.is_active
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-500/20 text-slate-400 border-slate-500/30'
                )}>
                  {vehicle.is_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                  {vehicle.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <p className="text-slate-muted">
                {[vehicle.make, vehicle.model, vehicle.model_year].filter(Boolean).join(' ') || 'Unknown Vehicle'}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="secondary" icon={X} onClick={cancelEditing}>
                Cancel
              </Button>
              <Button
                module="hr"
                icon={Save}
                onClick={handleSave}
                disabled={saving || !isLicensePlateValid}
                loading={saving}
              >
                Save
              </Button>
            </>
          ) : (
            <Button variant="secondary" icon={Edit} onClick={startEditing}>
              Edit
            </Button>
          )}
        </div>
      </div>

      {/* Insurance Alert */}
      {(insuranceExpiring || insuranceExpired) && (
        <div className={cn(
          'flex items-center gap-3 p-4 rounded-xl border',
          insuranceExpired
            ? 'bg-red-500/10 border-red-500/30'
            : 'bg-amber-500/10 border-amber-500/30'
        )}>
          <AlertTriangle className={insuranceExpired ? 'w-5 h-5 text-red-400' : 'w-5 h-5 text-amber-400'} />
          <div>
            <p className={cn('font-medium', insuranceExpired ? 'text-red-400' : 'text-amber-400')}>
              {insuranceExpired ? 'Insurance Expired' : 'Insurance Expiring Soon'}
            </p>
            <p className="text-sm text-slate-muted">
              {insuranceExpired
                ? `Insurance expired ${Math.abs(insuranceDays!)} days ago. Please renew immediately.`
                : `Insurance expires in ${insuranceDays} days (${formatDate(vehicle.insurance_end_date)})`}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Vehicle Details */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Vehicle Details</h3>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">License Plate</label>
                  <input
                    type="text"
                    value={editForm.license_plate}
                    onChange={(e) => handleFormChange('license_plate', e.target.value)}
                    required
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                  {formError && (
                    <p className="text-xs text-coral-alert mt-1">{formError}</p>
                  )}
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Make</label>
                  <input
                    type="text"
                    value={editForm.make}
                    onChange={(e) => handleFormChange('make', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Model</label>
                  <input
                    type="text"
                    value={editForm.model}
                    onChange={(e) => handleFormChange('model', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Model Year</label>
                  <input
                    type="number"
                    min="1900"
                    max="2100"
                    value={editForm.model_year}
                    onChange={(e) => handleFormChange('model_year', e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Color</label>
                  <input
                    type="text"
                    value={editForm.color}
                    onChange={(e) => handleFormChange('color', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Acquisition Date</label>
                  <input
                    type="date"
                    value={editForm.acquisition_date}
                    onChange={(e) => handleFormChange('acquisition_date', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Odometer</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={editForm.odometer_value}
                    onChange={(e) => {
                      const val = e.target.value;
                      // Preserve the raw value to avoid issues with empty input
                      handleFormChange('odometer_value', val === '' ? '' : parseFloat(val));
                    }}
                    onBlur={(e) => {
                      // On blur, ensure we have a valid number (default to previous value if empty)
                      const val = e.target.value;
                      if (val === '' || isNaN(parseFloat(val))) {
                        handleFormChange('odometer_value', vehicle?.odometer_value || 0);
                      }
                    }}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Fuel UOM</label>
                  <input
                    type="text"
                    value={editForm.fuel_uom}
                    onChange={(e) => handleFormChange('fuel_uom', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Location</label>
                  <input
                    type="text"
                    value={editForm.location}
                    onChange={(e) => handleFormChange('location', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Company</label>
                  <input
                    type="text"
                    value={editForm.company}
                    onChange={(e) => handleFormChange('company', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div className="col-span-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editForm.is_active}
                      onChange={(e) => handleFormChange('is_active', e.target.checked)}
                      className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-amber-500 focus:ring-amber-500/50"
                    />
                    <span className="text-foreground">Active</span>
                  </label>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <InfoRow icon={Hash} label="License Plate" value={vehicle.license_plate} iconColor="text-amber-400" />
                <InfoRow icon={Car} label="Make & Model" value={[vehicle.make, vehicle.model].filter(Boolean).join(' ') || '-'} />
                <InfoRow icon={Calendar} label="Year" value={vehicle.model_year || '-'} />
                <InfoRow icon={Palette} label="Color" value={vehicle.color || '-'} />
                <InfoRow icon={Hash} label="Chassis No" value={vehicle.chassis_no || '-'} />
                <InfoRow icon={Fuel} label="Fuel Type" value={vehicle.fuel_type || '-'} iconColor="text-emerald-400" />
                <InfoRow icon={Gauge} label="Odometer" value={`${formatNumber(vehicle.odometer_value)} ${vehicle.uom || 'km'}`} iconColor="text-cyan-400" />
                <InfoRow icon={Calendar} label="Last Odometer" value={formatDate(vehicle.last_odometer_date)} />
                <InfoRow icon={MapPin} label="Location" value={vehicle.location || '-'} iconColor="text-violet-400" />
                <InfoRow icon={DollarSign} label="Value" value={formatCurrency(vehicle.vehicle_value)} iconColor="text-amber-400" />
              </div>
            )}
          </div>

          {/* Insurance Details */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <div className="flex items-center gap-2 mb-4">
              <Shield className={cn(
                'w-5 h-5',
                insuranceExpired ? 'text-red-400' : insuranceExpiring ? 'text-amber-400' : 'text-emerald-400'
              )} />
              <h3 className="text-lg font-semibold text-foreground">Insurance</h3>
            </div>
            {isEditing ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Insurance Company</label>
                  <input
                    type="text"
                    value={editForm.insurance_company}
                    onChange={(e) => handleFormChange('insurance_company', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Policy Number</label>
                  <input
                    type="text"
                    value={editForm.policy_no}
                    onChange={(e) => handleFormChange('policy_no', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">Start Date</label>
                  <input
                    type="date"
                    value={editForm.insurance_start_date}
                    onChange={(e) => handleFormChange('insurance_start_date', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-muted mb-1 block">End Date</label>
                  <input
                    type="date"
                    value={editForm.insurance_end_date}
                    onChange={(e) => handleFormChange('insurance_end_date', e.target.value)}
                    className="w-full px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                  />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <InfoRow icon={Building2} label="Insurance Company" value={vehicle.insurance_company || '-'} />
                <InfoRow icon={FileText} label="Policy Number" value={vehicle.policy_no || '-'} />
                <InfoRow icon={Calendar} label="Start Date" value={formatDate(vehicle.insurance_start_date)} />
                <InfoRow
                  icon={Calendar}
                  label="End Date"
                  value={
                    <span className={cn(
                      insuranceExpired ? 'text-red-400' : insuranceExpiring ? 'text-amber-400' : 'text-foreground'
                    )}>
                      {formatDate(vehicle.insurance_end_date)}
                      {insuranceDays !== null && (
                        <span className="text-sm ml-2">
                          ({insuranceExpired ? `${Math.abs(insuranceDays)}d expired` : `${insuranceDays}d left`})
                        </span>
                      )}
                    </span>
                  }
                />
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Driver Assignment */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <div className="flex items-center gap-2 mb-4">
              <Users className="w-5 h-5 text-violet-400" />
              <h3 className="text-lg font-semibold text-foreground">Driver</h3>
            </div>
            {vehicle.driver_name ? (
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                  <Users className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                  <p className="text-foreground font-medium">{vehicle.driver_name}</p>
                  {vehicle.employee && (
                    <p className="text-slate-muted text-sm">ID: {vehicle.employee}</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <Users className="w-8 h-8 text-slate-muted mx-auto mb-2" />
                <p className="text-slate-muted text-sm">No driver assigned</p>
              </div>
            )}
          </div>

          {/* Specifications */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Specifications</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Doors</span>
                <span className="text-foreground">{vehicle.doors || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Wheels</span>
                <span className="text-foreground">{vehicle.wheels || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Fuel UOM</span>
                <span className="text-foreground">{vehicle.fuel_uom || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Company</span>
                <span className="text-foreground">{vehicle.company || '-'}</span>
              </div>
            </div>
          </div>

          {/* Timestamps */}
          <div className="bg-slate-card rounded-xl border border-slate-border p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-slate-muted" />
              <h3 className="text-lg font-semibold text-foreground">Timeline</h3>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Acquisition</span>
                <span className="text-foreground">{formatDate(vehicle.acquisition_date)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Created</span>
                <span className="text-foreground">{formatDate(vehicle.created_at)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-muted">Updated</span>
                <span className="text-foreground">{formatDate(vehicle.updated_at)}</span>
              </div>
            </div>
          </div>

          {/* ERPNext ID if available */}
          {vehicle.erpnext_id && (
            <div className="bg-slate-card rounded-xl border border-slate-border p-6">
              <h3 className="text-sm font-semibold text-slate-muted mb-2">ERPNext Reference</h3>
              <p className="text-foreground font-mono text-sm break-all">{vehicle.erpnext_id}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
