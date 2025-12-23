'use client';

import Link from 'next/link';
import { cn } from '@/lib/utils';
import { getQuickLinkColorClass } from './utils';
import type { QuickLink } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface QuickLinksGridProps {
  links: QuickLink[];
  /** Callback when navigating (e.g., to close mobile menu) */
  onNavigate?: () => void;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Grid of quick action links with icons
 */
export function QuickLinksGrid({ links, onNavigate }: QuickLinksGridProps) {
  if (!links || links.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-2">
      {links.map((link) => {
        const Icon = link.icon;
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            className="flex flex-col items-center p-2 rounded-lg bg-slate-elevated hover:bg-slate-border/30 transition-colors text-center"
          >
            <Icon className={cn('w-4 h-4 mb-1', getQuickLinkColorClass(link.color))} />
            <span className="text-xs text-slate-muted">{link.label}</span>
          </Link>
        );
      })}
    </div>
  );
}
