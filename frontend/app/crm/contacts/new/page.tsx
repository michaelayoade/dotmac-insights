'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
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
} from 'lucide-react';
import { useUnifiedContactMutations } from '@/hooks/useApi';
import { useFormErrors } from '@/hooks';
import { useRequireScope } from '@/lib/auth-context';
import { AccessDenied } from '@/components/AccessDenied';
import { Button } from '@/components/ui';

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
  contact_type: ContactType;
  category: ContactCategory;
  status: ContactStatus;
  is_organization: boolean;
  name: string;
  first_name: string;
  last_name: string;
  company_name: string;
  designation: string;
  department: string;
  email: string;
  billing_email: string;
  phone: string;
  phone_secondary: string;
  mobile: string;
  website: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  industry: string;
  territory: string;
  source: string;
  source_campaign: string;
  linkedin_url: string;
  twitter_handle: string;
  facebook_url: string;
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

export default function NewContactPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { createContact, isLoading, error } = useUnifiedContactMutations();
  const { hasAccess: canWrite, isLoading: authLoading } = useRequireScope('crm:write');

  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [newTag, setNewTag] = useState('');
  const { errors: validationErrors, setErrors: setValidationErrors, clearError } = useFormErrors();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  useEffect(() => {
    const typeParam = searchParams.get('type');
    if (typeParam && ['lead', 'prospect', 'customer', 'person'].includes(typeParam)) {
      setFormData((prev) => ({
        ...prev,
        contact_type: typeParam as ContactType,
        is_organization: typeParam === 'customer',
      }));
    }
  }, [searchParams]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-deep flex justify-center items-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400" />
      </div>
    );
  }

  if (!canWrite) {
    return (
      <div className="min-h-screen bg-slate-deep p-8">
        <AccessDenied />
      </div>
    );
  }

  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (validationErrors[field]) {
      clearError(field);
    }
  };

  const addTag = () => {
    if (newTag.trim() && !formData.tags.includes(newTag.trim())) {
      updateField('tags', [...formData.tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    updateField('tags', formData.tags.filter((t) => t !== tag));
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.name.trim()) {
      if (formData.is_organization) {
        errors.name = 'Company/organization name is required';
      } else if (!formData.first_name.trim() && !formData.last_name.trim()) {
        errors.name = 'Name is required';
      }
    }

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Invalid email format';
    }

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
      let name = formData.name.trim();
      if (!name && (formData.first_name || formData.last_name)) {
        name = `${formData.first_name} ${formData.last_name}`.trim();
      }

      const payload = {
        ...formData,
        name,
        tags: formData.tags.length > 0 ? formData.tags : undefined,
      };

      const cleanedPayload = Object.fromEntries(
        Object.entries(payload).filter(([_, v]) => v !== '' && v !== undefined)
      );

      await createContact(cleanedPayload);
      setSubmitSuccess(true);

      setTimeout(() => {
        router.push('/crm');
      }, 1500);
    } catch (err) {
      console.error('Failed to create contact:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link
          href="/crm"
          className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">New Contact</h1>
          <p className="text-slate-400 text-sm">Add a new contact to your CRM</p>
        </div>
      </div>

      {/* Success Message */}
      {submitSuccess && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3">
          <Check className="w-5 h-5 text-emerald-400" />
          <span className="text-emerald-300">Contact created successfully! Redirecting...</span>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="text-red-300">Failed to create contact. Please try again.</span>
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
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Category</label>
              <select
                value={formData.category}
                onChange={(e) => updateField('category', e.target.value as ContactCategory)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground focus:outline-none focus:border-cyan-500"
              >
                {Object.entries(categoryLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-2">Status</label>
              <select
                value={formData.status}
                onChange={(e) => updateField('status', e.target.value as ContactStatus)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/50 border border-slate-600 text-foreground focus:outline-none focus:border-cyan-500"
              >
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>

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
            ) : (
              <>
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
                  <p className="mt-1 text-xs text-slate-500">Leave blank to use first + last name</p>
                </div>
              </>
            )}

            {!formData.is_organization && (
              <>
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
              </>
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
                <Button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="hover:text-foreground transition-colors"
                >
                  &times;
                </Button>
              </span>
            ))}
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
            <Button
              type="button"
              onClick={addTag}
              className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-foreground transition-colors"
            >
              Add
            </Button>
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

        {/* Submit Buttons */}
        <div className="flex justify-end gap-4">
          <Link
            href="/crm"
            className="px-6 py-3 rounded-lg border border-slate-600 text-foreground-secondary hover:bg-slate-800 transition-colors"
          >
            Cancel
          </Link>
          <Button
            type="submit"
            disabled={isSubmitting || submitSuccess}
            className="px-6 py-3 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-foreground font-medium hover:from-cyan-600 hover:to-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Creating...
              </>
            ) : submitSuccess ? (
              <>
                <Check className="w-5 h-5" />
                Created!
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                Create Contact
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
