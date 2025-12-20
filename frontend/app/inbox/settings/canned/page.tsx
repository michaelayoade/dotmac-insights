'use client';

import { MessageCircle } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxCannedResponsesPage() {
  return (
    <PlaceholderPage
      title="Canned Responses"
      subtitle="Quick replies"
      message="Canned response management is coming soon."
      icon={MessageCircle}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
