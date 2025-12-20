'use client';

import { Users } from 'lucide-react';
import { PlaceholderPage } from '@/components/PlaceholderPage';

export default function InboxRoutingTeamsPage() {
  return (
    <PlaceholderPage
      title="Routing Teams"
      subtitle="Team queues and assignment"
      message="Team routing configuration is coming soon."
      icon={Users}
      backHref="/inbox"
      backLabel="Back to Inbox"
    />
  );
}
