'use client';

import Link from 'next/link';
import { ArrowLeft, type LucideIcon } from 'lucide-react';
import { PageHeader } from '@/components/ui';
import { EmptyState } from '@/components/insights/shared';

interface PlaceholderPageProps {
  title: string;
  subtitle?: string;
  message: string;
  icon: LucideIcon;
  backHref?: string;
  backLabel?: string;
}

export function PlaceholderPage({
  title,
  subtitle,
  message,
  icon: Icon,
  backHref,
  backLabel = 'Back',
}: PlaceholderPageProps) {
  return (
    <div className="space-y-6">
      <PageHeader
        title={title}
        subtitle={subtitle}
        icon={Icon as LucideIcon}
        iconClassName="bg-slate-elevated border border-slate-border"
        actions={
          backHref ? (
            <Link
              href={backHref}
              className="flex items-center gap-2 px-4 py-2 bg-slate-elevated text-foreground rounded-lg hover:bg-slate-border transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              {backLabel}
            </Link>
          ) : null
        }
      />
      <EmptyState
        title="Coming soon"
        message={message}
        icon={<Icon className="w-8 h-8 text-slate-muted" />}
      />
    </div>
  );
}

export default PlaceholderPage;
