'use client';

import { useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import useSWR from 'swr';
import {
  ArrowLeft,
  MapPin,
  Calendar,
  Clock,
  User,
  Phone,
  Mail,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Play,
  Pause,
  Navigation,
  Camera,
  FileText,
  Package,
  DollarSign,
  Star,
  Edit2,
  Truck,
  ClipboardCheck,
  Upload,
  X,
  Loader2,
  Car,
  Box,
} from 'lucide-react';
import { fieldServiceApi } from '@/lib/api';
import { cn } from '@/lib/utils';

const statusConfig: Record<string, { color: string; bg: string; label: string; icon: any }> = {
  draft: { color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Draft', icon: FileText },
  scheduled: { color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Scheduled', icon: Calendar },
  dispatched: { color: 'text-purple-400', bg: 'bg-purple-500/10', label: 'Dispatched', icon: Truck },
  en_route: { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'En Route', icon: Navigation },
  on_site: { color: 'text-cyan-400', bg: 'bg-cyan-500/10', label: 'On Site', icon: MapPin },
  in_progress: { color: 'text-teal-400', bg: 'bg-teal-500/10', label: 'In Progress', icon: Play },
  completed: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'Completed', icon: CheckCircle2 },
  cancelled: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Cancelled', icon: XCircle },
  rescheduled: { color: 'text-orange-400', bg: 'bg-orange-500/10', label: 'Rescheduled', icon: Calendar },
  failed: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Failed', icon: XCircle },
};

const priorityConfig: Record<string, { color: string; bg: string }> = {
  emergency: { color: 'text-red-500', bg: 'bg-red-500/10' },
  urgent: { color: 'text-orange-500', bg: 'bg-orange-500/10' },
  high: { color: 'text-amber-500', bg: 'bg-amber-500/10' },
  medium: { color: 'text-blue-500', bg: 'bg-blue-500/10' },
  low: { color: 'text-slate-400', bg: 'bg-slate-400/10' },
};

type TabType = 'overview' | 'checklist' | 'time' | 'photos' | 'items';

export default function ServiceOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isUpdating, setIsUpdating] = useState(false);
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [selectedTechnician, setSelectedTechnician] = useState<number | null>(null);
  const [dispatchNotes, setDispatchNotes] = useState('');
  const [notifyCustomer, setNotifyCustomer] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadPhotoType, setUploadPhotoType] = useState<string>('issue');
  const [uploadCaption, setUploadCaption] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: order, isLoading, mutate } = useSWR(
    params.id ? `field-service-order-${params.id}` : null,
    () => fieldServiceApi.getOrder(params.id as string)
  );

  const { data: technicians } = useSWR(
    showDispatchModal ? 'field-service-technicians' : null,
    () => fieldServiceApi.getTechnicians().then(r => r.data || [])
  );

  const updateStatus = async (action: string, payload?: any) => {
    setIsUpdating(true);
    setErrorMessage(null);
    try {
      await fieldServiceApi.updateOrderStatus(params.id as string, action, payload);
      mutate();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail?.message) {
        setErrorMessage(detail.message);
      } else if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else {
        setErrorMessage('Failed to update order status');
      }
      console.error('Failed to update status:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDispatch = async () => {
    if (!selectedTechnician) {
      setErrorMessage('Please select a technician');
      return;
    }

    setIsUpdating(true);
    setErrorMessage(null);
    try {
      await fieldServiceApi.dispatchOrder(params.id as string, {
        technician_id: selectedTechnician,
        notes: dispatchNotes,
        notify_customer: notifyCustomer,
      });
      setShowDispatchModal(false);
      setSelectedTechnician(null);
      setDispatchNotes('');
      mutate();
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'object' && detail?.message) {
        setErrorMessage(detail.message);
      } else if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else {
        setErrorMessage('Failed to dispatch order');
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const handlePhotoUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('photo_type', uploadPhotoType);
    if (uploadCaption) {
      formData.append('caption', uploadCaption);
    }

    try {
      // Let the client set multipart headers automatically
      await fieldServiceApi.uploadPhoto(params.id as string, formData);
      mutate();
      setUploadCaption('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'Failed to upload photo');
    } finally {
      setIsUploading(false);
    }
  }, [params.id, uploadPhotoType, uploadCaption, mutate]);

  const handleDeletePhoto = async (photoId: number) => {
    if (!confirm('Are you sure you want to delete this photo?')) return;

    try {
      await fieldServiceApi.deletePhoto(params.id as string, photoId);
      mutate();
    } catch (error) {
      setErrorMessage('Failed to delete photo');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-card rounded animate-pulse" />
        <div className="h-64 bg-slate-card border border-slate-border rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!order) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
        <p className="text-lg text-foreground mb-2">Order not found</p>
        <Link href="/field-service/orders" className="text-teal-electric hover:underline">
          Back to orders
        </Link>
      </div>
    );
  }

  const checklistGroups = order.checklists ?? order.checklist ?? [];
  const timeEntries = order.time_entries ?? [];
  const photos = order.photos ?? [];
  const items = order.items ?? [];

  const status = statusConfig[order.status] || statusConfig.draft;
  const priority = priorityConfig[order.priority] || priorityConfig.medium;
  const StatusIcon = status.icon;

  const tabs: { key: TabType; label: string; icon: any }[] = [
    { key: 'overview', label: 'Overview', icon: FileText },
    { key: 'checklist', label: 'Checklist', icon: ClipboardCheck },
    { key: 'time', label: 'Time Entries', icon: Clock },
    { key: 'photos', label: 'Photos', icon: Camera },
    { key: 'items', label: 'Parts & Items', icon: Package },
  ];

  // Status workflow actions
  const getAvailableActions = () => {
    const actions: { label: string; action: string; color: string; icon: any; payload?: any }[] = [];

    switch (order.status) {
      case 'draft':
        actions.push({ label: 'Schedule', action: 'schedule', color: 'bg-blue-500', icon: Calendar });
        break;
      case 'scheduled':
        actions.push({ label: 'Dispatch', action: 'dispatch', color: 'bg-purple-500', icon: Truck });
        break;
      case 'dispatched':
        actions.push({ label: 'En Route', action: 'start-travel', color: 'bg-amber-500', icon: Navigation });
        break;
      case 'en_route':
        actions.push({ label: 'Arrived', action: 'arrive', color: 'bg-cyan-500', icon: MapPin });
        break;
      case 'on_site':
        actions.push({ label: 'Start Work', action: 'start-work', color: 'bg-teal-500', icon: Play });
        break;
      case 'in_progress':
        actions.push({ label: 'Complete', action: 'complete', color: 'bg-green-500', icon: CheckCircle2 });
        break;
    }

    // Cancel is always available for non-terminal states
    if (!['completed', 'cancelled', 'failed'].includes(order.status)) {
      actions.push({ label: 'Cancel', action: 'cancel', color: 'bg-red-500/80', icon: XCircle });
    }

    return actions;
  };

  const availableActions = getAvailableActions();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/field-service/orders"
            className="inline-flex items-center gap-1 text-slate-muted hover:text-foreground text-sm mb-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to orders
          </Link>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-foreground">{order.order_number}</h2>
            <span className={cn('px-2 py-1 rounded text-xs font-medium capitalize', priority.color, priority.bg)}>
              {order.priority}
            </span>
            <span className={cn('px-2 py-1 rounded text-xs font-medium flex items-center gap-1', status.color, status.bg)}>
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
          </div>
          <p className="text-slate-muted mt-1">{order.title}</p>
        </div>

        <div className="flex items-center gap-2">
          {availableActions.map((action) => (
            <button
              key={action.action}
              onClick={() => {
                if (action.action === 'dispatch') {
                  setShowDispatchModal(true);
                } else {
                  updateStatus(action.action, action.payload);
                }
              }}
              disabled={isUpdating}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-foreground transition-colors disabled:opacity-50',
                action.color,
                action.action === 'cancel' ? 'hover:bg-red-600' : 'hover:opacity-90'
              )}
            >
              {isUpdating && <Loader2 className="w-4 h-4 animate-spin" />}
              {!isUpdating && <action.icon className="w-4 h-4" />}
              {action.label}
            </button>
          ))}
          <Link
            href={`/field-service/orders/${order.id}/edit`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            <Edit2 className="w-4 h-4" />
            Edit
          </Link>
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Tabs */}
          <div className="bg-slate-card border border-slate-border rounded-xl">
            <div className="border-b border-slate-border px-4">
              <nav className="flex gap-1 -mb-px">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={cn(
                      'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                      activeTab === tab.key
                        ? 'border-teal-electric text-teal-electric'
                        : 'border-transparent text-slate-muted hover:text-foreground'
                    )}
                  >
                    <tab.icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            <div className="p-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  <div>
                    <h4 className="text-sm font-medium text-slate-muted mb-2">Description</h4>
                    <p className="text-foreground">{order.description || 'No description provided'}</p>
                  </div>

                  {order.notes && (
                    <div>
                      <h4 className="text-sm font-medium text-slate-muted mb-2">Internal Notes</h4>
                      <p className="text-slate-muted">{order.notes}</p>
                    </div>
                  )}

                  {order.resolution_notes && (
                    <div>
                      <h4 className="text-sm font-medium text-slate-muted mb-2">Resolution Notes</h4>
                      <p className="text-foreground">{order.resolution_notes}</p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-medium text-slate-muted mb-2">Service Type</h4>
                      <p className="text-foreground capitalize">{order.order_type?.replace('_', ' ') || 'General'}</p>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-slate-muted mb-2">Estimated Duration</h4>
                      <p className="text-foreground">
                        {order.estimated_duration
                          ? `${order.estimated_duration} mins`
                          : order.estimated_duration_minutes
                            ? `${order.estimated_duration_minutes} mins`
                            : 'Not set'}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'checklist' && (
                <div>
                  {checklistGroups.length > 0 ? (
                    <div className="space-y-4">
                      {checklistGroups.map((checklist: any) => (
                        <div key={checklist.id} className="space-y-2">
                          <h4 className="text-foreground font-medium">{checklist.template_name || 'Checklist'}</h4>
                          <div className="space-y-1">
                            {checklist.items?.map((item: any, idx: number) => (
                              <div
                                key={idx}
                                className={cn(
                                  'flex items-center gap-3 p-2 rounded-lg',
                                  item.checked ? 'bg-green-500/10' : 'bg-slate-elevated'
                                )}
                              >
                                <div className={cn(
                                  'w-5 h-5 rounded border flex items-center justify-center',
                                  item.checked ? 'bg-green-500 border-green-500' : 'border-slate-border'
                                )}>
                                  {item.checked && <CheckCircle2 className="w-3 h-3 text-foreground" />}
                                </div>
                                <span className={cn(
                                  'text-sm',
                                  item.checked ? 'text-green-400' : 'text-foreground'
                                )}>
                                  {item.item_name}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-slate-muted text-center py-8">No checklist assigned</p>
                  )}
                </div>
              )}

              {activeTab === 'time' && (
                <div>
                  {timeEntries.length > 0 ? (
                    <div className="space-y-3">
                      {timeEntries.map((entry: any) => (
                        <div key={entry.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-elevated">
                          <div>
                            <p className="text-foreground text-sm capitalize">{entry.entry_type.replace('_', ' ')}</p>
                            <p className="text-slate-muted text-xs">
                              {new Date(entry.start_time).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-foreground font-medium">
                              {entry.duration_minutes ? `${entry.duration_minutes} mins` : 'In progress'}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-slate-muted text-center py-8">No time entries recorded</p>
                  )}
                </div>
              )}

              {activeTab === 'photos' && (
                <div className="space-y-4">
                  {/* Photo Upload */}
                  <div className="border-2 border-dashed border-slate-border rounded-lg p-6">
                    <div className="flex flex-col items-center gap-4">
                      <div className="flex items-center gap-4">
                        <select
                          value={uploadPhotoType}
                          onChange={(e) => setUploadPhotoType(e.target.value)}
                          className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground text-sm focus:outline-none focus:border-teal-electric/50"
                        >
                          <option value="before">Before</option>
                          <option value="after">After</option>
                          <option value="issue">Issue</option>
                          <option value="equipment">Equipment</option>
                          <option value="location">Location</option>
                        </select>
                        <input
                          type="text"
                          placeholder="Caption (optional)"
                          value={uploadCaption}
                          onChange={(e) => setUploadCaption(e.target.value)}
                          className="px-3 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground text-sm focus:outline-none focus:border-teal-electric/50"
                        />
                      </div>
                      <label className="cursor-pointer">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/*"
                          onChange={handlePhotoUpload}
                          className="hidden"
                          disabled={isUploading}
                        />
                        <div className={cn(
                          'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                          isUploading
                            ? 'bg-slate-elevated text-slate-muted'
                            : 'bg-teal-electric text-slate-950 hover:bg-teal-electric/90'
                        )}>
                          {isUploading ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Uploading...
                            </>
                          ) : (
                            <>
                              <Upload className="w-4 h-4" />
                              Upload Photo
                            </>
                          )}
                        </div>
                      </label>
                    </div>
                  </div>

                  {/* Photo Grid */}
                  {photos.length > 0 ? (
                    <div className="grid grid-cols-3 gap-4">
                      {photos.map((photo: any) => (
                        <div key={photo.id} className="relative aspect-square rounded-lg bg-slate-elevated overflow-hidden group">
                          <Image
                            src={photo.file_url || `/api/field-service/photos/${photo.id}`}
                            alt={photo.caption || 'Service photo'}
                            fill
                            className="object-cover"
                            unoptimized
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <button
                              onClick={() => handleDeletePhoto(photo.id)}
                              className="p-2 bg-red-500 rounded-full text-foreground hover:bg-red-600 transition-colors"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                          <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1">
                            <p className="text-xs text-slate-muted capitalize">{photo.photo_type}</p>
                            {photo.caption && (
                              <p className="text-xs text-foreground truncate">{photo.caption}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-slate-muted text-center py-8">No photos uploaded yet</p>
                  )}
                </div>
              )}

              {activeTab === 'items' && (
                <div>
                  {items.length > 0 ? (
                    <table className="w-full">
                      <thead>
                        <tr className="text-left text-xs text-slate-muted">
                          <th className="pb-2">Item</th>
                          <th className="pb-2">Qty</th>
                          <th className="pb-2 text-right">Price</th>
                          <th className="pb-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-border">
                        {items.map((item: any) => (
                          <tr key={item.id}>
                            <td className="py-2 text-foreground">{item.item_name}</td>
                            <td className="py-2 text-slate-muted">{item.quantity}</td>
                            <td className="py-2 text-right text-slate-muted">₦{item.unit_price?.toLocaleString()}</td>
                            <td className="py-2 text-right text-foreground">₦{item.total_price?.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="text-slate-muted text-center py-8">No parts or items used</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column - Info Cards */}
        <div className="space-y-6">
          {/* Schedule Info */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-teal-electric" />
              Schedule
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-slate-muted text-sm">Scheduled Date</span>
                <span className="text-foreground text-sm">
                  {order.scheduled_date
                    ? new Date(order.scheduled_date).toLocaleDateString('en-NG', {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                      })
                    : 'Not scheduled'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-muted text-sm">Time Window</span>
                <span className="text-foreground text-sm">
                  {order.scheduled_start_time || 'TBD'} - {order.scheduled_end_time || 'TBD'}
                </span>
              </div>
              {order.actual_start_time && (
                <div className="flex justify-between">
                  <span className="text-slate-muted text-sm">Actual Start</span>
                  <span className="text-foreground text-sm">
                    {new Date(order.actual_start_time).toLocaleTimeString()}
                  </span>
                </div>
              )}
              {order.actual_end_time && (
                <div className="flex justify-between">
                  <span className="text-slate-muted text-sm">Actual End</span>
                  <span className="text-foreground text-sm">
                    {new Date(order.actual_end_time).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Customer Info */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-teal-electric" />
              Customer
            </h3>
            {order.customer_id ? (
              <div className="space-y-3">
                <p className="text-foreground font-medium">{order.customer_name}</p>
                {order.customer_phone && (
                  <div className="flex items-center gap-2 text-slate-muted text-sm">
                    <Phone className="w-4 h-4" />
                    {order.customer_phone}
                  </div>
                )}
                {order.customer_email && (
                  <div className="flex items-center gap-2 text-slate-muted text-sm">
                    <Mail className="w-4 h-4" />
                    {order.customer_email}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-muted text-sm">No customer assigned</p>
            )}
          </div>

          {/* Location Info */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-teal-electric" />
              Location
            </h3>
            <div className="space-y-2 text-sm">
              {order.address && <p className="text-foreground">{order.address}</p>}
              {(order.city || order.state) && (
                <p className="text-slate-muted">{[order.city, order.state].filter(Boolean).join(', ')}</p>
              )}
              {order.latitude && order.longitude && (
                <a
                  href={`https://maps.google.com/?q=${order.latitude},${order.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-teal-electric hover:underline mt-2"
                >
                  <Navigation className="w-3 h-3" />
                  Open in Maps
                </a>
              )}
            </div>
          </div>

          {/* Technician Info */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
              <Truck className="w-4 h-4 text-teal-electric" />
              Assigned Technician
            </h3>
            {order.technician_id ? (
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-slate-elevated flex items-center justify-center">
                  <User className="w-5 h-5 text-slate-muted" />
                </div>
                <div>
                  <p className="text-foreground font-medium">{order.technician_name}</p>
                  {order.team_name && (
                    <p className="text-slate-muted text-sm">{order.team_name}</p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-amber-400 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Not assigned
              </p>
            )}
          </div>

          {/* Related Asset */}
          {order.asset_id && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
                <Box className="w-4 h-4 text-teal-electric" />
                Related Asset
              </h3>
              <Link
                href={`/assets/list/${order.asset_id}`}
                className="text-foreground hover:text-teal-electric transition-colors"
              >
                <p className="font-medium">{order.asset_name || `Asset #${order.asset_id}`}</p>
                {order.asset_code && (
                  <p className="text-slate-muted text-sm">{order.asset_code}</p>
                )}
              </Link>
            </div>
          )}

          {/* Related Vehicle */}
          {order.vehicle_id && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
                <Car className="w-4 h-4 text-teal-electric" />
                Related Vehicle
              </h3>
              <Link
                href={`/hr/fleet/${order.vehicle_id}`}
                className="text-foreground hover:text-teal-electric transition-colors"
              >
                <p className="font-medium">{order.vehicle_name || order.license_plate || `Vehicle #${order.vehicle_id}`}</p>
                {order.vehicle_model && (
                  <p className="text-slate-muted text-sm">{order.vehicle_model}</p>
                )}
              </Link>
            </div>
          )}

          {/* Financials */}
          <div className="bg-slate-card border border-slate-border rounded-xl p-5">
            <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-teal-electric" />
              Financials
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-slate-muted text-sm">Labor Cost</span>
                <span className="text-foreground text-sm">
                  ₦{(order.labor_cost || 0).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-muted text-sm">Parts Cost</span>
                <span className="text-foreground text-sm">
                  ₦{(order.parts_cost || 0).toLocaleString()}
                </span>
              </div>
              <div className="border-t border-slate-border pt-3 flex justify-between">
                <span className="text-foreground font-medium">Total</span>
                <span className="text-foreground font-bold">
                  ₦{(order.total_cost || 0).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Customer Rating */}
          {order.customer_rating !== undefined && order.customer_rating !== null && (
            <div className="bg-slate-card border border-slate-border rounded-xl p-5">
              <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
                <Star className="w-4 h-4 text-amber-400" />
                Customer Feedback
              </h3>
              <div className="flex items-center gap-2 mb-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <Star
                    key={star}
                    className={cn(
                      'w-5 h-5',
                      star <= (order.customer_rating || 0)
                        ? 'text-amber-400 fill-amber-400'
                        : 'text-slate-600'
                    )}
                  />
                ))}
              </div>
              {order.customer_feedback && (
                <p className="text-slate-muted text-sm">{order.customer_feedback}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Dispatch Modal */}
      {showDispatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setShowDispatchModal(false)}
          />
          <div className="relative bg-slate-card border border-slate-border rounded-xl w-full max-w-lg p-6 shadow-xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Truck className="w-5 h-5 text-teal-electric" />
                Dispatch Order
              </h3>
              <button
                onClick={() => setShowDispatchModal(false)}
                className="p-1 text-slate-muted hover:text-foreground transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Technician Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-muted mb-2">
                  Select Technician *
                </label>
                <select
                  value={selectedTechnician || ''}
                  onChange={(e) => setSelectedTechnician(Number(e.target.value) || null)}
                  className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
                >
                  <option value="">Choose a technician...</option>
                  {technicians?.map((tech: any) => (
                    <option key={tech.id} value={tech.id}>
                      {tech.employee_name} {tech.team_name ? `(${tech.team_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-slate-muted mb-2">
                  Dispatch Notes
                </label>
                <textarea
                  value={dispatchNotes}
                  onChange={(e) => setDispatchNotes(e.target.value)}
                  placeholder="Optional notes for the technician..."
                  rows={3}
                  className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder:text-slate-muted focus:outline-none focus:border-teal-electric/50 resize-none"
                />
              </div>

              {/* Notify Customer */}
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notifyCustomer}
                  onChange={(e) => setNotifyCustomer(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-border bg-slate-elevated text-teal-electric focus:ring-teal-electric/50"
                />
                <span className="text-sm text-foreground">Notify customer about technician assignment</span>
              </label>

              {/* Error in modal */}
              {errorMessage && showDispatchModal && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-sm text-red-400">
                  {errorMessage}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-border">
                <button
                  onClick={() => setShowDispatchModal(false)}
                  className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDispatch}
                  disabled={isUpdating || !selectedTechnician}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500 text-foreground font-medium hover:bg-purple-600 transition-colors disabled:opacity-50"
                >
                  {isUpdating && <Loader2 className="w-4 h-4 animate-spin" />}
                  Dispatch
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
