'use client';

import { NavSectionsList } from './NavSection';
import { QuickLinksGrid } from './QuickLinks';
import { WorkflowIndicator, WorkflowSteps } from './WorkflowIndicator';
import type { QuickLink, WorkflowStep } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface ModuleSidebarProps {
  /** Sidebar title */
  sidebarTitle: string;
  /** Sidebar description */
  sidebarDescription: string;
  /** Optional quick links */
  quickLinks?: QuickLink[];
  /** Optional workflow steps */
  workflowSteps?: WorkflowStep[];
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Desktop sidebar with navigation sections, workflow indicator, and quick links
 */
export function ModuleSidebar({
  sidebarTitle,
  sidebarDescription,
  quickLinks,
  workflowSteps,
}: ModuleSidebarProps) {
  return (
    <aside className="hidden lg:block bg-slate-card border border-slate-border rounded-xl p-4 space-y-4 h-fit">
      {/* Header */}
      <div className="pb-3 border-b border-slate-border">
        <h1 className="text-lg font-semibold text-foreground">{sidebarTitle}</h1>
        <p className="text-slate-muted text-xs mt-1">{sidebarDescription}</p>
      </div>

      {/* Workflow Phase Indicator */}
      <WorkflowIndicator />

      {/* Navigation Sections */}
      <NavSectionsList />

      {/* Quick Links */}
      {quickLinks && quickLinks.length > 0 && (
        <div className="pt-3 border-t border-slate-border">
          <p className="text-xs text-slate-muted mb-2 px-1">Quick Links</p>
          <QuickLinksGrid links={quickLinks} />
        </div>
      )}

      {/* Workflow Steps Guide */}
      {workflowSteps && workflowSteps.length > 0 && <WorkflowSteps steps={workflowSteps} />}
    </aside>
  );
}
