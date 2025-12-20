'use client';

import { BarChart3 } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxAgentAnalyticsPage() {
  return (
    <PlaceholderPage
      title="Agent Analytics"
      subtitle="Response times and workload"
      message="Agent analytics for inbox is coming soon."
      icon={BarChart3}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
