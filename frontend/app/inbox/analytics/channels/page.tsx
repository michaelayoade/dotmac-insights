'use client';

import { MessageSquare } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxChannelAnalyticsPage() {
  return (
    <PlaceholderPage
      title="Channel Analytics"
      subtitle="Performance by channel"
      message="Channel analytics will be available soon."
      icon={MessageSquare}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
