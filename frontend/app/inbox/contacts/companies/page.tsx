'use client';

import { Building2 } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxCompaniesPage() {
  return (
    <PlaceholderPage
      title="Company Contacts"
      subtitle="Organization directory"
      message="Company contact views are coming soon."
      icon={Building2}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
