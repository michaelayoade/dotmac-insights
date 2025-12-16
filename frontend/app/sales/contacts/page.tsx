'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  MoreHorizontal,
  Phone,
  Mail,
  Building2,
  User,
  Star,
  Briefcase,
  Linkedin,
} from 'lucide-react';
import { useContacts, useContactMutations } from '@/hooks/useApi';
import type { Contact } from '@/lib/api';

export default function ContactsPage() {
  const [search, setSearch] = useState('');
  const [isPrimary, setIsPrimary] = useState<string>('');
  const [isDecisionMaker, setIsDecisionMaker] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data: contacts, isLoading } = useContacts({
    search: search || undefined,
    is_primary: isPrimary === '' ? undefined : isPrimary === 'true',
    is_decision_maker: isDecisionMaker === '' ? undefined : isDecisionMaker === 'true',
    page,
    page_size: 20,
  });

  const { setPrimaryContact } = useContactMutations();

  const handleSetPrimary = async (id: number) => {
    try {
      await setPrimaryContact(id);
    } catch (error) {
      console.error('Failed to set primary contact:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Contacts</h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage contacts across customers and leads
          </p>
        </div>
        <Link
          href="/sales/contacts/new"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Contact
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search contacts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
        </div>
        <select
          value={isPrimary}
          onChange={(e) => setIsPrimary(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Contacts</option>
          <option value="true">Primary Only</option>
          <option value="false">Non-Primary</option>
        </select>
        <select
          value={isDecisionMaker}
          onChange={(e) => setIsDecisionMaker(e.target.value)}
          className="px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          <option value="">All Roles</option>
          <option value="true">Decision Makers</option>
        </select>
      </div>

      {/* Contacts Grid */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
          </div>
        ) : contacts?.items?.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <User className="w-12 h-12 mb-4 opacity-50" />
            <p>No contacts found</p>
            <Link
              href="/sales/contacts/new"
              className="mt-4 text-emerald-400 hover:text-emerald-300"
            >
              Add your first contact
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
            {contacts?.items?.map((contact: Contact) => (
              <div
                key={contact.id}
                className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white font-medium text-lg">
                      {contact.full_name?.charAt(0) || '?'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{contact.full_name}</span>
                        {contact.is_primary && (
                          <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                        )}
                      </div>
                      {contact.designation && (
                        <div className="text-sm text-slate-400 flex items-center gap-1">
                          <Briefcase className="w-3 h-3" />
                          {contact.designation}
                        </div>
                      )}
                    </div>
                  </div>
                  <button className="p-1.5 text-slate-400 hover:bg-slate-700/50 rounded-lg transition-colors">
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                </div>

                <div className="mt-4 space-y-2">
                  {contact.email && (
                    <a
                      href={`mailto:${contact.email}`}
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      <Mail className="w-4 h-4" />
                      {contact.email}
                    </a>
                  )}
                  {contact.phone && (
                    <a
                      href={`tel:${contact.phone}`}
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      <Phone className="w-4 h-4" />
                      {contact.phone}
                    </a>
                  )}
                  {contact.mobile && (
                    <a
                      href={`tel:${contact.mobile}`}
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      <Phone className="w-4 h-4" />
                      {contact.mobile}
                    </a>
                  )}
                  {contact.linkedin_url && (
                    <a
                      href={contact.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      <Linkedin className="w-4 h-4" />
                      LinkedIn
                    </a>
                  )}
                </div>

                <div className="mt-4 pt-4 border-t border-slate-700/50 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {contact.customer_id && (
                      <Link
                        href={`/sales/customers/${contact.customer_id}`}
                        className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        <Building2 className="w-3 h-3" />
                        Customer
                      </Link>
                    )}
                    {contact.lead_id && (
                      <Link
                        href={`/sales/leads/${contact.lead_id}`}
                        className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300"
                      >
                        <User className="w-3 h-3" />
                        Lead
                      </Link>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {contact.is_decision_maker && (
                      <span className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">
                        Decision Maker
                      </span>
                    )}
                    {contact.is_billing_contact && (
                      <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                        Billing
                      </span>
                    )}
                  </div>
                </div>

                {!contact.is_primary && (
                  <button
                    onClick={() => handleSetPrimary(contact.id)}
                    className="mt-3 w-full px-3 py-1.5 text-xs bg-slate-700/50 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg transition-colors"
                  >
                    Set as Primary
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {contacts && contacts.total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
            <div className="text-sm text-slate-400">
              Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, contacts.total)} of {contacts.total}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * 20 >= contacts.total}
                className="px-3 py-1.5 text-sm bg-slate-700/50 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
