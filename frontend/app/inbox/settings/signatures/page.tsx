'use client';

import { FileText } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxSignaturesPage() {
  return (
    <PlaceholderPage
      title="Signatures"
      subtitle="Email signature templates"
      message="Signature settings are coming soon."
      icon={FileText}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
