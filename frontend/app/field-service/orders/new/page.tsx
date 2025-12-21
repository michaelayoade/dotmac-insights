'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import {
  ArrowLeft,
  Save,
  MapPin,
  Calendar,
  User,
  AlertTriangle,
  ClipboardList,
  Clock,
} from 'lucide-react';
import { fieldServiceApi, customersApi, FieldServiceOrderPriority, FieldServiceOrderCreatePayload } from '@/lib/api';
import { cn } from '@/lib/utils';

const orderTypes = [
  { value: 'installation', label: 'Installation' },
  { value: 'repair', label: 'Repair' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'inspection', label: 'Inspection' },
  { value: 'consultation', label: 'Consultation' },
  { value: 'emergency', label: 'Emergency Service' },
  { value: 'follow_up', label: 'Follow Up' },
  { value: 'other', label: 'Other' },
];

const priorities = [
  { value: 'emergency', label: 'Emergency', color: 'text-red-500' },
  { value: 'urgent', label: 'Urgent', color: 'text-orange-500' },
  { value: 'high', label: 'High', color: 'text-amber-500' },
  { value: 'medium', label: 'Medium', color: 'text-blue-500' },
  { value: 'low', label: 'Low', color: 'text-slate-400' },
];

export default function NewServiceOrderPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    title: '',
    description: '',
    order_type: 'maintenance',
    priority: 'medium',
    customer_id: '',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    address: '',
    city: '',
    state: '',
    postal_code: '',
    latitude: '',
    longitude: '',
    scheduled_date: '',
    scheduled_start_time: '',
    scheduled_end_time: '',
    estimated_duration: '',
    assigned_team_id: '',
    assigned_technician_id: '',
    notes: '',
    checklist_template_id: '',
  });

  // Fetch customers for selection
  const { data: customers } = useSWR('customers-list', () =>
    customersApi.getCustomers({ limit: 100 }).then((r: any) => r.items || r.data || r.customers || [])
  );

  // Fetch teams for selection
  const { data: teams } = useSWR('field-teams', () =>
    fieldServiceApi.getTeams().then(r => r.data || [])
  );

  // Fetch checklist templates
  const { data: checklistTemplates } = useSWR('checklist-templates', () =>
    fieldServiceApi.getChecklistTemplates().then(r => r.data || [])
  );

  // Get technicians for selected team
  const selectedTeam = teams?.find((t: any) => t.id === parseInt(formData.assigned_team_id));
  const technicians = selectedTeam?.members || [];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
      // Reset technician if team changes
      ...(name === 'assigned_team_id' ? { assigned_technician_id: '' } : {}),
    }));
  };

  const handleCustomerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const customerId = e.target.value;
    const customer = customers?.find((c: any) => c.id === parseInt(customerId));

    setFormData(prev => ({
      ...prev,
      customer_id: customerId,
      contact_name: customer?.contact_name || customer?.name || '',
      contact_phone: customer?.phone || '',
      contact_email: customer?.email || '',
      address: customer?.address || '',
      city: customer?.city || '',
      state: customer?.state || '',
    }));
  };

  const handleSubmit = async (e: React.FormEvent, createAnother = false) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const payload: FieldServiceOrderCreatePayload & {
        technician_id?: number | null;
        contact_name?: string;
        contact_phone?: string;
        contact_email?: string;
        postal_code?: string;
      } = {
        ...formData,
        priority: formData.priority as FieldServiceOrderPriority,
        customer_id: formData.customer_id ? parseInt(formData.customer_id) : undefined,
        team_id: formData.assigned_team_id ? parseInt(formData.assigned_team_id) : undefined,
        technician_id: formData.assigned_technician_id ? parseInt(formData.assigned_technician_id) : undefined,
        estimated_duration_minutes: formData.estimated_duration ? parseInt(formData.estimated_duration) : undefined,
        latitude: formData.latitude ? parseFloat(formData.latitude) : undefined,
        longitude: formData.longitude ? parseFloat(formData.longitude) : undefined,
        checklist_template_id: formData.checklist_template_id ? parseInt(formData.checklist_template_id) : undefined,
        scheduled_date: formData.scheduled_date || undefined,
        scheduled_start_time: formData.scheduled_start_time || undefined,
        scheduled_end_time: formData.scheduled_end_time || undefined,
        postal_code: formData.postal_code || undefined,
      };

      const response = await fieldServiceApi.createOrder(payload);

      if (createAnother) {
        // Reset form
        setFormData({
          title: '',
          description: '',
          order_type: 'maintenance',
          priority: 'medium',
          customer_id: '',
          contact_name: '',
          contact_phone: '',
          contact_email: '',
          address: '',
          city: '',
          state: '',
          postal_code: '',
          latitude: '',
          longitude: '',
          scheduled_date: '',
          scheduled_start_time: '',
          scheduled_end_time: '',
          estimated_duration: '',
          assigned_team_id: '',
          assigned_technician_id: '',
          notes: '',
          checklist_template_id: '',
        });
      } else {
        router.push(`/field-service/orders/${response.id}`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/field-service/orders"
          className="inline-flex items-center gap-1 text-slate-muted hover:text-foreground text-sm mb-2 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to orders
        </Link>
        <h2 className="text-xl font-semibold text-foreground">New Service Order</h2>
        <p className="text-sm text-slate-muted">Create a new field service order</p>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      <form onSubmit={(e) => handleSubmit(e)} className="space-y-6">
        {/* Basic Info */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-teal-electric" />
            Basic Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                placeholder="e.g., AC Installation at Customer Office"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Service Type</label>
              <select
                name="order_type"
                value={formData.order_type}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              >
                {orderTypes.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Priority</label>
              <select
                name="priority"
                value={formData.priority}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              >
                {priorities.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={3}
                placeholder="Describe the service to be performed..."
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50 resize-none"
              />
            </div>
          </div>
        </div>

        {/* Customer Info */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <User className="w-4 h-4 text-teal-electric" />
            Customer Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">Select Customer</label>
              <select
                name="customer_id"
                value={formData.customer_id}
                onChange={handleCustomerChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              >
                <option value="">Select a customer...</option>
                {customers?.map((customer: any) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} {customer.company_name ? `(${customer.company_name})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Contact Name</label>
              <input
                type="text"
                name="contact_name"
                value={formData.contact_name}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Contact Phone</label>
              <input
                type="tel"
                name="contact_phone"
                value={formData.contact_phone}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">Contact Email</label>
              <input
                type="email"
                name="contact_email"
                value={formData.contact_email}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
          </div>
        </div>

        {/* Location */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-teal-electric" />
            Service Location
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">Address</label>
              <input
                type="text"
                name="address"
                value={formData.address}
                onChange={handleChange}
                placeholder="Street address"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">City</label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">State</label>
              <input
                type="text"
                name="state"
                value={formData.state}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Latitude (optional)</label>
              <input
                type="text"
                name="latitude"
                value={formData.latitude}
                onChange={handleChange}
                placeholder="e.g., 6.5244"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Longitude (optional)</label>
              <input
                type="text"
                name="longitude"
                value={formData.longitude}
                onChange={handleChange}
                placeholder="e.g., 3.3792"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
          </div>
        </div>

        {/* Schedule */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-teal-electric" />
            Schedule
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Scheduled Date</label>
              <input
                type="date"
                name="scheduled_date"
                value={formData.scheduled_date}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Estimated Duration (minutes)</label>
              <input
                type="number"
                name="estimated_duration"
                value={formData.estimated_duration}
                onChange={handleChange}
                placeholder="e.g., 60"
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Start Time</label>
              <input
                type="time"
                name="scheduled_start_time"
                value={formData.scheduled_start_time}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">End Time</label>
              <input
                type="time"
                name="scheduled_end_time"
                value={formData.scheduled_end_time}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              />
            </div>
          </div>
        </div>

        {/* Assignment */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <User className="w-4 h-4 text-teal-electric" />
            Assignment
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Team</label>
              <select
                name="assigned_team_id"
                value={formData.assigned_team_id}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              >
                <option value="">Select a team...</option>
                {teams?.map((team: any) => (
                  <option key={team.id} value={team.id}>{team.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-muted mb-1">Technician</label>
              <select
                name="assigned_technician_id"
                value={formData.assigned_technician_id}
                onChange={handleChange}
                disabled={!formData.assigned_team_id}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50 disabled:opacity-50"
              >
                <option value="">Select a technician...</option>
                {technicians?.map((tech: any) => (
                  <option key={tech.employee_id} value={tech.employee_id}>
                    {tech.employee_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-muted mb-1">Checklist Template</label>
              <select
                name="checklist_template_id"
                value={formData.checklist_template_id}
                onChange={handleChange}
                className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground focus:outline-none focus:border-teal-electric/50"
              >
                <option value="">No checklist</option>
                {checklistTemplates?.map((template: any) => (
                  <option key={template.id} value={template.id}>{template.name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="bg-slate-card border border-slate-border rounded-xl p-6">
          <h3 className="text-foreground font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-teal-electric" />
            Internal Notes
          </h3>
          <textarea
            name="notes"
            value={formData.notes}
            onChange={handleChange}
            rows={3}
            placeholder="Add any internal notes for the technician..."
            className="w-full px-4 py-2 bg-slate-elevated border border-slate-border rounded-lg text-foreground placeholder-slate-muted focus:outline-none focus:border-teal-electric/50 resize-none"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <Link
            href="/field-service/orders"
            className="px-4 py-2 rounded-lg border border-slate-border text-slate-muted hover:text-foreground hover:border-slate-border/70 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="button"
            onClick={(e) => handleSubmit(e, true)}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg border border-teal-electric text-teal-electric hover:bg-teal-electric/10 transition-colors disabled:opacity-50"
          >
            Save & Create Another
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-6 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 transition-colors disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {isSubmitting ? 'Creating...' : 'Create Order'}
          </button>
        </div>
      </form>
    </div>
  );
}
