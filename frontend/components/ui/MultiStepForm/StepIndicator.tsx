'use client';

import { cn } from '@/lib/utils';
import { Check, AlertCircle, SkipForward } from 'lucide-react';
import type { FormStep, StepStatus } from './types';

// =============================================================================
// STEP INDICATOR
// =============================================================================

export interface StepIndicatorProps {
  /** Step definitions */
  steps: FormStep[];
  /** Current step index */
  currentStep: number;
  /** Step statuses */
  stepStatuses: StepStatus[];
  /** Callback when step is clicked */
  onStepClick?: (index: number) => void;
  /** Allow navigation to previous steps */
  allowNavigation?: boolean;
  /** Orientation */
  orientation?: 'horizontal' | 'vertical';
  /** Show step numbers */
  showNumbers?: boolean;
  /** Custom class name */
  className?: string;
}

export function StepIndicator({
  steps,
  currentStep,
  stepStatuses,
  onStepClick,
  allowNavigation = true,
  orientation = 'horizontal',
  showNumbers = true,
  className,
}: StepIndicatorProps) {
  const isHorizontal = orientation === 'horizontal';

  const getStepIcon = (status: StepStatus, index: number) => {
    switch (status) {
      case 'completed':
        return <Check className="w-4 h-4" />;
      case 'error':
        return <AlertCircle className="w-4 h-4" />;
      case 'skipped':
        return <SkipForward className="w-4 h-4" />;
      default:
        return showNumbers ? <span className="text-sm font-medium">{index + 1}</span> : null;
    }
  };

  const getStepColors = (status: StepStatus, isActive: boolean) => {
    if (isActive) {
      return {
        circle: 'bg-teal-electric text-foreground border-teal-electric',
        line: 'bg-teal-electric',
        text: 'text-foreground',
      };
    }

    switch (status) {
      case 'completed':
        return {
          circle: 'bg-emerald-500 text-foreground border-emerald-500',
          line: 'bg-emerald-500',
          text: 'text-foreground',
        };
      case 'error':
        return {
          circle: 'bg-coral-alert/20 text-coral-alert border-coral-alert',
          line: 'bg-slate-border',
          text: 'text-coral-alert',
        };
      case 'skipped':
        return {
          circle: 'bg-slate-elevated text-slate-muted border-slate-border',
          line: 'bg-slate-border',
          text: 'text-slate-muted',
        };
      default:
        return {
          circle: 'bg-slate-elevated text-slate-muted border-slate-border',
          line: 'bg-slate-border',
          text: 'text-slate-muted',
        };
    }
  };

  const handleStepClick = (index: number) => {
    if (!allowNavigation) return;
    if (!onStepClick) return;

    // Can only navigate to completed, error, or current steps
    const status = stepStatuses[index];
    if (status === 'completed' || status === 'error' || index === currentStep) {
      onStepClick(index);
    }
  };

  return (
    <div
      className={cn(
        'flex',
        isHorizontal ? 'flex-row items-start' : 'flex-col',
        className
      )}
    >
      {steps.map((step, index) => {
        const status = stepStatuses[index] || 'pending';
        const isActive = index === currentStep;
        const isLast = index === steps.length - 1;
        const colors = getStepColors(status, isActive);
        const canClick = allowNavigation && (status === 'completed' || status === 'error' || isActive);

        return (
          <div
            key={step.id}
            className={cn(
              'flex',
              isHorizontal ? 'flex-1 flex-col items-center' : 'flex-row items-start',
              !isLast && (isHorizontal ? '' : 'pb-8')
            )}
          >
            {/* Step Circle and Line */}
            <div
              className={cn(
                'flex',
                isHorizontal ? 'flex-row items-center w-full' : 'flex-col items-center'
              )}
            >
              {/* Circle */}
              <button
                type="button"
                onClick={() => handleStepClick(index)}
                disabled={!canClick}
                className={cn(
                  'relative flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all',
                  colors.circle,
                  canClick && 'cursor-pointer hover:scale-105',
                  !canClick && 'cursor-default'
                )}
              >
                {getStepIcon(status, index)}

                {/* Pulse animation for current step */}
                {isActive && (
                  <span className="absolute inset-0 rounded-full animate-ping bg-teal-electric/20" />
                )}
              </button>

              {/* Connecting Line */}
              {!isLast && (
                <div
                  className={cn(
                    isHorizontal
                      ? 'flex-1 h-0.5 mx-2'
                      : 'w-0.5 flex-1 min-h-[2rem] my-2',
                    status === 'completed' || (isActive && index < steps.length - 1)
                      ? colors.line
                      : 'bg-slate-border'
                  )}
                />
              )}
            </div>

            {/* Step Label */}
            <div
              className={cn(
                'mt-2',
                isHorizontal ? 'text-center' : 'ml-4 -mt-10'
              )}
            >
              <p className={cn('text-sm font-medium', colors.text)}>
                {step.title}
                {step.optional && (
                  <span className="ml-1 text-xs text-slate-muted">(optional)</span>
                )}
              </p>
              {step.description && (
                <p className="text-xs text-slate-muted mt-0.5 max-w-[120px]">
                  {step.description}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default StepIndicator;
