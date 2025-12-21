'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Save,
  User,
  Building2,
  Mail,
  Phone,
  MapPin,
  Tag,
  Globe,
  Briefcase,
  Target,
  AlertCircle,
  Check,
  Loader2,
  Trash2,
  Archive,
  AlertTriangle,
  X,
} from 'lucide-react';
import { useUnifiedContact, useUnifiedContactMutations } from '@/hooks/useApi';
import type { Contact as CRMContact } from '@/lib/api';
import { useRequireScope, useAuth } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';

type ContactType = 'lead' | 'prospect' | 'customer' | 'person' | 'churned';
type ContactCategory = 'residential' | 'business' | 'enterprise' | 'government' | 'nonprofit';
type ContactStatus = 'active' | 'inactive' | 'suspended' | 'do_not_contact';

const contactTypeLabels: Record<ContactType, string> = {
  lead: 'Lead',
  prospect: 'Prospect',
  customer: 'Customer',
  person: 'Person',
  churned: 'Churned',
};

const categoryLabels: Record<ContactCategory, string> = {
  residential: 'Residential',
  business: 'Business',
  enterprise: 'Enterprise',
  government: 'Government',
  nonprofit: 'Non-Profit',
};

const statusLabels: Record<ContactStatus, string> = {
  active: 'Active',
  inactive: 'Inactive',
  suspended: 'Suspended',
  do_not_contact: 'Do Not Contact',
};

interface FormData {
  // Type and classification
  contact_type: ContactType;
  category: ContactCategory;
  status: ContactStatus;
  is_organization: boolean;

  // Basic info
  name: string;
  first_name: string;
  last_name: string;
  company_name: string;
  designation: string;
  department: string;

  // Contact info
  email: string;
  billing_email: string;
  phone: string;
  phone_secondary: string;
  mobile: string;
  website: string;

  // Address
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;

  // Business info
  industry: string;
  territory: string;
  source: string;
  source_campaign: string;

  // Social
  linkedin_url: string;
  twitter_handle: string;
  facebook_url: string;

  // Notes
  notes: string;
  tags: string[];
}

const initialFormData: FormData = {
  contact_type: 'lead',
  category: 'residential',
  status: 'active',
  is_organization: false,

  name: '',
  first_name: '',
  last_name: '',
  company_name: '',
  designation: '',
  department: '',

  email: '',
  billing_email: '',
  phone: '',
  phone_secondary: '',
  mobile: '',
  website: '',

  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  postal_code: '',
  country: 'Nigeria',

  industry: '',
  territory: '',
  source: '',
  source_campaign: '',

  linkedin_url: '',
  twitter_handle: '',
  facebook_url: '',

  notes: '',
  tags: [],
};

export default function EditContactPage() {
  const router = useRouter();
  const params = useParams();
  const contactId = Number(params.id);

  // RBAC check - require write permission to edit contacts
  const { hasAccess, isLoading: authLoading } = useRequireScope('contacts:write');
  const { hasAnyScope } = useAuth();
  const canHardDelete = hasAnyScope(['admin:write', '*']);

  const { data: contactData, isLoading: isLoadingContact, error: loadError } = useUnifiedContact(contactId);
  const contact = useMemo(() => (contactData as CRMContact | undefined) || ({} as CRMContact), [contactData]);
  const { updateContact, deleteContact, isLoading: isUpdating, error: updateError } = useUnifiedContactMutations();

  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [newTag, setNewTag] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [showArchiveDialog, setShowArchiveDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Load contact data into form
  useEffect(() => {
    if (contact) {
      setFormData({
        contact_type: (contact.contact_type as ContactType | undefined) || 'lead',
        category: (contact.category as ContactCategory | undefined) || 'residential',
        status: (contact.status as ContactStatus | undefined) || 'active',
        is_organization: contact.is_organization || false,

        name: contact.name || '',
        first_name: contact.first_name || '',
        last_name: contact.last_name || '',
        company_name: contact.company_name || '',
        designation: contact.designation || '',
        department: contact.department || '',

        email: contact.email || '',
        billing_email: contact.billing_email || '',
        phone: contact.phone || '',
        phone_secondary: contact.phone_secondary || '',
        mobile: contact.mobile || '',
        website: contact.website || '',

        address_line1: contact.address_line1 || '',
        address_line2: contact.address_line2 || '',
        city: contact.city || '',
        state: contact.state || '',
        postal_code: contact.postal_code || '',
        country: contact.country || 'Nigeria',

        industry: contact.industry || '',
        territory: contact.territory || '',
        source: contact.source || '',
        source_campaign: contact.source_campaign || '',

        linkedin_url: contact.linkedin_url || '',
        twitter_handle: contact.twitter_handle || '',
        facebook_url: contact.facebook_url || '',

        notes: contact.notes || '',
        tags: contact.tags || [],
      });
    }
  }, [contact]);

  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
    // Clear validation error when field is updated
    if (validationErrors[field]) {
      setValidationErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const addTag = () => {
    if (newTag.trim() && !formData.tags.includes(newTag.trim())) {
      updateField('tags', [...formData.tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    updateField(
      'tags',
      formData.tags.filter((t) => t !== tag)
    );
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    // Name is required
    if (!formData.name.trim()) {
      if (formData.is_organization) {
        errors.name = 'Company/organization name is required';
      } else if (!formData.first_name.trim() && !formData.last_name.trim()) {
        errors.name = 'Name is required';
      }
    }

    // Email validation
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Invalid email format';
    }

    // Phone validation (basic)
    if (formData.phone && !/^[\d\s\-+()]+$/.test(formData.phone)) {
      errors.phone = 'Invalid phone format';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      // Compute name if not provided
      let name = formData.name.trim();
      if (!name && (formData.first_name || formData.last_name)) {
        name = `${formData.first_name} ${formData.last_name}`.trim();
      }

      const payload = {
        ...formData,
        name,
        tags: formData.tags.length > 0 ? formData.tags : undefined,
      };

      // Remove empty strings, keep null/undefined to clear fields
      const cleanedPayload = Object.fromEntries(
        Object.entries(payload).filter(([_, v]) => v !== '')
      );

      await updateContact(contactId, cleanedPayload);
      setSubmitSuccess(true);
      setHasChanges(false);

      // Redirect after short delay
      setTimeout(() => {
        router.push(`/contacts/${contactId}`);
      }, 1500);
    } catch (err) {
      console.error('Failed to update contact:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchive = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteContact(contactId, false);
      router.push('/contacts');
    } catch (err) {
      console.error('Failed to archive contact:', err);
      setDeleteError('Failed to archive contact. Please try again.');
    } finally {
      setIsDeleting(false);
      setShowArchiveDialog(false);
    }
  };

  const handlePermanentDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteContact(contactId, true);
      router.push('/contacts');
    } catch (err) {
      console.error('Failed to delete contact:', err);
      setDeleteError('Failed to permanently delete contact. Please try again.');
    } finally {
      setIsDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  if (authLoading || isLoadingContact) {
    return (
      <div className="p-6 flex justify-center items-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400" />
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <AccessDenied
        message="You need contacts:write permission to edit contacts."
        backHref={`/contacts/${contactId}`}
        backLabel="Back to Contact"
      />
    );
  }

  if (loadError || !contact) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-foreground mb-2">Contact Not Found</h2>
          <p className="text-slate-400 mb-4">The contact you are trying to edit does not exist.</p>
          <Link
            href="/contacts"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Contacts
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link
          href={`/contacts/${contactId}`}
          className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Edit Contact</h1>
          <p className="text-slate-400 text-sm">Update {contact.name}</p>
        </div>
      </div>

      {/* Success Message */}
      {submitSuccess && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3">
          <Check className="w-5 h-5 text-emerald-400" />
          <span className="text-emerald-300">Contact updated successfully! Redirecting...</span>
        </div>
      )}

      {/* Error Message */}
      {updateError && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="text-red-300">Failed to update contact. Please try again.</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Type & Classification */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-cyan-400" />
            Classification
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Contact Type */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">
                Contact Type
              </label>
              <select
                value={formData.contact_type}
                onChange={(e) => updateField('contact_type', e.target.value as ContactType)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground focus:outline-none focus:border-cyan-500"
              >
                {Object.entries(contactTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Category */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Category</label>
              <select
                value={formData.category}
                onChange={(e) => updateField('category', e.target.value as ContactCategory)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground focus:outline-none focus:border-cyan-500"
              >
                {Object.entries(categoryLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Status */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Status</label>
              <select
                value={formData.status}
                onChange={(e) => updateField('status', e.target.value as ContactStatus)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground focus:outline-none focus:border-cyan-500"
              >
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Is Organization Toggle */}
          <div className="mt-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_organization}
                onChange={(e) => updateField('is_organization', e.target.checked)}
                className="w-5 h-5 rounded border-slate-600 bg-slate-900/50 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-800"
              />
              <span className="text-foreground-secondary">This is an organization/company</span>
            </label>
          </div>
        </div>

        {/* Basic Information */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            {formData.is_organization ? (
              <Building2 className="w-5 h-5 text-cyan-400" />
            ) : (
              <User className="w-5 h-5 text-cyan-400" />
            )}
            Basic Information
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {formData.is_organization ? (
              <>
                {/* Organization Name */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-foreground-secondary mb-2">
                    Organization Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder="Enter organization name"
                    className={`w-full px-3 py-2 rounded-lg bg-slate-900/50 border ${
                      validationErrors.name ? 'border-red-500' : 'border-slate-600'
                    } text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500`}
                  />
                  {validationErrors.name && (
                    <p className="mt-1 text-sm text-red-400">{validationErrors.name}</p>
                  )}
                </div>
              </>
            ) : (
              <>
                {/* First Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground-secondary mb-2">
                    First Name
                  </label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => updateField('first_name', e.target.value)}
                    placeholder="First name"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Last Name */}
                <div>
                  <label className="block text-sm font-medium text-foreground-secondary mb-2">Last Name</label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => updateField('last_name', e.target.value)}
                    placeholder="Last name"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Display Name */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-foreground-secondary mb-2">
                    Display Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder="Full name or display name"
                    className={`w-full px-3 py-2 rounded-lg bg-slate-900/50 border ${
                      validationErrors.name ? 'border-red-500' : 'border-slate-600'
                    } text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500`}
                  />
                  {validationErrors.name && (
                    <p className="mt-1 text-sm text-red-400">{validationErrors.name}</p>
                  )}
                  <p className="mt-1 text-xs text-slate-500">
                    Leave blank to use first + last name
                  </p>
                </div>
              </>
            )}

            {/* Company (for people) */}
            {!formData.is_organization && (
              <div>
                <label className="block text-sm font-medium text-foreground-secondary mb-2">Company</label>
                <input
                  type="text"
                  value={formData.company_name}
                  onChange={(e) => updateField('company_name', e.target.value)}
                  placeholder="Company name"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            )}

            {/* Job Title / Designation */}
            {!formData.is_organization && (
              <div>
                <label className="block text-sm font-medium text-foreground-secondary mb-2">Job Title</label>
                <input
                  type="text"
                  value={formData.designation}
                  onChange={(e) => updateField('designation', e.target.value)}
                  placeholder="Job title"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            )}

            {/* Department */}
            {!formData.is_organization && (
              <div>
                <label className="block text-sm font-medium text-foreground-secondary mb-2">Department</label>
                <input
                  type="text"
                  value={formData.department}
                  onChange={(e) => updateField('department', e.target.value)}
                  placeholder="Department"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Contact Information */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Mail className="w-5 h-5 text-cyan-400" />
            Contact Information
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => updateField('email', e.target.value)}
                placeholder="email@example.com"
                className={`w-full px-3 py-2 rounded-lg bg-slate-900/50 border ${
                  validationErrors.email ? 'border-red-500' : 'border-slate-600'
                } text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500`}
              />
              {validationErrors.email && (
                <p className="mt-1 text-sm text-red-400">{validationErrors.email}</p>
              )}
            </div>

            {/* Billing Email */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Billing Email</label>
              <input
                type="email"
                value={formData.billing_email}
                onChange={(e) => updateField('billing_email', e.target.value)}
                placeholder="billing@example.com"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => updateField('phone', e.target.value)}
                placeholder="+234 xxx xxx xxxx"
                className={`w-full px-3 py-2 rounded-lg bg-slate-900/50 border ${
                  validationErrors.phone ? 'border-red-500' : 'border-slate-600'
                } text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500`}
              />
              {validationErrors.phone && (
                <p className="mt-1 text-sm text-red-400">{validationErrors.phone}</p>
              )}
            </div>

            {/* Mobile */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Mobile</label>
              <input
                type="tel"
                value={formData.mobile}
                onChange={(e) => updateField('mobile', e.target.value)}
                placeholder="+234 xxx xxx xxxx"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Secondary Phone */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">
                Secondary Phone
              </label>
              <input
                type="tel"
                value={formData.phone_secondary}
                onChange={(e) => updateField('phone_secondary', e.target.value)}
                placeholder="+234 xxx xxx xxxx"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Website */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Website</label>
              <input
                type="url"
                value={formData.website}
                onChange={(e) => updateField('website', e.target.value)}
                placeholder="https://example.com"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Address */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-cyan-400" />
            Address
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Address Line 1 */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-foreground-secondary mb-2">
                Address Line 1
              </label>
              <input
                type="text"
                value={formData.address_line1}
                onChange={(e) => updateField('address_line1', e.target.value)}
                placeholder="Street address"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Address Line 2 */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-foreground-secondary mb-2">
                Address Line 2
              </label>
              <input
                type="text"
                value={formData.address_line2}
                onChange={(e) => updateField('address_line2', e.target.value)}
                placeholder="Suite, unit, building, etc."
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* City */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">City</label>
              <input
                type="text"
                value={formData.city}
                onChange={(e) => updateField('city', e.target.value)}
                placeholder="City"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* State */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">State</label>
              <input
                type="text"
                value={formData.state}
                onChange={(e) => updateField('state', e.target.value)}
                placeholder="State"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Postal Code */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Postal Code</label>
              <input
                type="text"
                value={formData.postal_code}
                onChange={(e) => updateField('postal_code', e.target.value)}
                placeholder="Postal code"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Country */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Country</label>
              <input
                type="text"
                value={formData.country}
                onChange={(e) => updateField('country', e.target.value)}
                placeholder="Country"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Business Information */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-cyan-400" />
            Business Information
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Industry */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Industry</label>
              <input
                type="text"
                value={formData.industry}
                onChange={(e) => updateField('industry', e.target.value)}
                placeholder="Industry"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Territory */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Territory</label>
              <input
                type="text"
                value={formData.territory}
                onChange={(e) => updateField('territory', e.target.value)}
                placeholder="Territory / Region"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Source */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Lead Source</label>
              <input
                type="text"
                value={formData.source}
                onChange={(e) => updateField('source', e.target.value)}
                placeholder="e.g., Website, Referral, Event"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Campaign */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Campaign</label>
              <input
                type="text"
                value={formData.source_campaign}
                onChange={(e) => updateField('source_campaign', e.target.value)}
                placeholder="Campaign name"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Social Links */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Globe className="w-5 h-5 text-cyan-400" />
            Social Profiles
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* LinkedIn */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">LinkedIn</label>
              <input
                type="url"
                value={formData.linkedin_url}
                onChange={(e) => updateField('linkedin_url', e.target.value)}
                placeholder="https://linkedin.com/in/..."
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Twitter */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Twitter</label>
              <input
                type="text"
                value={formData.twitter_handle}
                onChange={(e) => updateField('twitter_handle', e.target.value)}
                placeholder="@username"
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Facebook */}
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Facebook</label>
              <input
                type="url"
                value={formData.facebook_url}
                onChange={(e) => updateField('facebook_url', e.target.value)}
                placeholder="https://facebook.com/..."
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Tags */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Tag className="w-5 h-5 text-cyan-400" />
            Tags
          </h2>

          <div className="flex flex-wrap gap-2 mb-4">
            {formData.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300 text-sm"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="hover:text-foreground transition-colors"
                >
                  &times;
                </button>
              </span>
            ))}
            {formData.tags.length === 0 && (
              <span className="text-slate-500 text-sm">No tags added</span>
            )}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag();
                }
              }}
              placeholder="Add a tag..."
              className="flex-1 px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
            <button
              type="button"
              onClick={addTag}
              className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-foreground transition-colors"
            >
              Add
            </button>
          </div>
        </div>

        {/* Notes */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">Notes</h2>
          <textarea
            value={formData.notes}
            onChange={(e) => updateField('notes', e.target.value)}
            placeholder="Additional notes about this contact..."
            rows={4}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none"
          />
        </div>

        {/* Danger Zone */}
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 mt-8">
          <h2 className="text-lg font-semibold text-red-400 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" />
            Danger Zone
          </h2>
          <p className="text-slate-400 text-sm mb-4">
            Actions here cannot be easily undone. Please proceed with caution.
          </p>

          {deleteError && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <span className="text-red-300 text-sm">{deleteError}</span>
            </div>
          )}

          <div className="space-y-4">
            {/* Archive (Soft Delete) */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-slate-700">
              <div>
                <h3 className="text-foreground font-medium">Archive Contact</h3>
                <p className="text-slate-400 text-sm">
                  Mark this contact as inactive. They will be hidden from active lists but can be restored.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowArchiveDialog(true)}
                className="px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30 transition-colors flex items-center gap-2"
              >
                <Archive className="w-4 h-4" />
                Archive
              </button>
            </div>

            {/* Permanent Delete - Admin Only */}
            {canHardDelete && (
              <div className="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-red-500/20">
                <div>
                  <h3 className="text-foreground font-medium">Permanently Delete</h3>
                  <p className="text-slate-400 text-sm">
                    Permanently remove this contact and all associated data. This action cannot be undone.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowDeleteDialog(true)}
                  className="px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 transition-colors flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Submit Buttons */}
        <div className="flex justify-between items-center">
          <div>
            {hasChanges && (
              <span className="text-sm text-amber-400">You have unsaved changes</span>
            )}
          </div>
          <div className="flex gap-4">
            <Link
              href={`/contacts/${contactId}`}
              className="px-6 py-3 rounded-lg border border-slate-600 text-foreground-secondary hover:bg-slate-800 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={isSubmitting || submitSuccess || !hasChanges}
              className="px-6 py-3 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-foreground font-medium hover:from-cyan-600 hover:to-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : submitSuccess ? (
                <>
                  <Check className="w-5 h-5" />
                  Saved!
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Archive Confirmation Dialog */}
      {showArchiveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowArchiveDialog(false)} />
          <div className="relative bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <Archive className="w-5 h-5 text-amber-400" />
                Archive Contact
              </h3>
              <button
                onClick={() => setShowArchiveDialog(false)}
                className="p-1 rounded hover:bg-slate-700 transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <p className="text-foreground-secondary mb-6">
              Are you sure you want to archive <strong>{contact.name}</strong>?
              The contact will be marked as inactive and hidden from active lists, but can be restored later.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowArchiveDialog(false)}
                className="px-4 py-2 rounded-lg border border-slate-600 text-foreground-secondary hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg bg-amber-500 text-foreground hover:bg-amber-400 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Archiving...
                  </>
                ) : (
                  <>
                    <Archive className="w-4 h-4" />
                    Archive Contact
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Permanent Delete Confirmation Dialog */}
      {showDeleteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowDeleteDialog(false)} />
          <div className="relative bg-slate-800 border border-red-500/30 rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-red-400 flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                Permanently Delete Contact
              </h3>
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="p-1 rounded hover:bg-slate-700 transition-colors"
              >
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg mb-4">
              <p className="text-red-300 text-sm flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                This action cannot be undone. All data associated with this contact will be permanently deleted.
              </p>
            </div>
            <p className="text-foreground-secondary mb-6">
              Are you sure you want to permanently delete <strong>{contact.name}</strong>?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="px-4 py-2 rounded-lg border border-slate-600 text-foreground-secondary hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handlePermanentDelete}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg bg-red-500 text-foreground hover:bg-red-400 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Delete Permanently
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
