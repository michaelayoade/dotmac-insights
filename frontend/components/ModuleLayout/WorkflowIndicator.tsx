'use client';

import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModuleLayoutContext } from './context';
import { getWorkflowStepClasses } from './utils';
import type { WorkflowStep } from './types';

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Workflow phase indicator with clickable pills
 */
export function WorkflowIndicator() {
  const { colors, baseRoute, sections, workflowPhases, getWorkflowPhase, currentPhase } =
    useModuleLayoutContext();

  if (!workflowPhases || workflowPhases.length === 0) return null;

  return (
    <div className="bg-slate-elevated rounded-lg p-3">
      <p className="text-xs text-slate-muted mb-2">Workflow Phase</p>
      <div className="flex flex-wrap items-center gap-1">
        {workflowPhases.map((phase, idx) => {
          // Find the section that maps to this workflow phase
          const matchingSection = getWorkflowPhase
            ? sections.find((s) => getWorkflowPhase(s.key) === phase.key)
            : sections[idx];
          const phaseHref = matchingSection?.items[0]?.href || baseRoute;

          return (
            <div key={phase.key} className="flex items-center">
              <Link
                href={phaseHref}
                className={cn(
                  'px-2 py-1 rounded text-xs font-medium transition-colors cursor-pointer hover:opacity-80',
                  currentPhase === phase.key
                    ? `${colors.activeItemBg} ${colors.activeItemText} border ${colors.activeBorder}`
                    : 'text-slate-muted hover:text-foreground hover:bg-slate-border/30'
                )}
                title={phase.description}
              >
                {phase.label}
              </Link>
              {idx < workflowPhases.length - 1 && (
                <ChevronRight className="w-3 h-3 text-slate-muted mx-1 flex-shrink-0" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// WORKFLOW STEPS
// =============================================================================

interface WorkflowStepsProps {
  steps: WorkflowStep[];
}

/**
 * Numbered workflow steps guide
 */
export function WorkflowSteps({ steps }: WorkflowStepsProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="pt-3 border-t border-slate-border">
      <p className="text-xs text-slate-muted mb-2 px-1">Workflow</p>
      <div className="space-y-1 text-[10px] text-slate-muted px-1">
        {steps.map((step, idx) => {
          const colors = getWorkflowStepClasses(step.color);
          return (
            <div key={idx} className="flex items-center gap-2">
              <div
                className={cn(
                  'w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold',
                  colors.bg,
                  colors.text
                )}
              >
                {idx + 1}
              </div>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
