'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight, Check, Loader2 } from 'lucide-react';
import { StepIndicator } from './StepIndicator';
import type { FormStep, StepStatus, StepState, MultiStepFormState } from './types';

// =============================================================================
// MULTI-STEP FORM
// =============================================================================

export interface MultiStepFormProps {
  /** Step definitions */
  steps: FormStep[];
  /** Initial form data */
  initialData?: Record<string, unknown>;
  /** Callback when form is submitted */
  onSubmit: (data: Record<string, unknown>) => Promise<void> | void;
  /** Callback when step changes */
  onStepChange?: (stepIndex: number, direction: 'next' | 'prev') => void;
  /** Callback when data changes */
  onDataChange?: (data: Record<string, unknown>) => void;
  /** Render function for step content */
  renderStep: (
    step: FormStep,
    stepIndex: number,
    data: Record<string, unknown>,
    updateData: (field: string, value: unknown) => void,
    errors: Record<string, string>,
    setErrors: (errors: Record<string, string>) => void
  ) => React.ReactNode;
  /** Show step indicator */
  showIndicator?: boolean;
  /** Indicator position */
  indicatorPosition?: 'top' | 'left';
  /** Allow step navigation via indicator */
  allowStepNavigation?: boolean;
  /** Show progress percentage */
  showProgress?: boolean;
  /** Custom next button label */
  nextButtonLabel?: string;
  /** Custom previous button label */
  prevButtonLabel?: string;
  /** Custom submit button label */
  submitButtonLabel?: string;
  /** Hide navigation buttons */
  hideNavigation?: boolean;
  /** Custom class name */
  className?: string;
  /** Step content class name */
  contentClassName?: string;
  /** Navigation class name */
  navigationClassName?: string;
}

export function MultiStepForm({
  steps,
  initialData = {},
  onSubmit,
  onStepChange,
  onDataChange,
  renderStep,
  showIndicator = true,
  indicatorPosition = 'top',
  allowStepNavigation = true,
  showProgress = false,
  nextButtonLabel = 'Next',
  prevButtonLabel = 'Back',
  submitButtonLabel = 'Submit',
  hideNavigation = false,
  className,
  contentClassName,
  navigationClassName,
}: MultiStepFormProps) {
  // Form state
  const [state, setState] = useState<MultiStepFormState>(() => ({
    currentStepIndex: 0,
    steps: steps.map((step) => ({
      id: step.id,
      status: 'pending' as StepStatus,
      data: {},
      errors: {},
      touched: false,
    })),
    isSubmitting: false,
    isComplete: false,
  }));

  // Merged form data from all steps
  const formData = useMemo(() => {
    const merged = { ...initialData };
    state.steps.forEach((stepState) => {
      Object.assign(merged, stepState.data);
    });
    return merged;
  }, [state.steps, initialData]);

  // Current step
  const currentStep = steps[state.currentStepIndex];
  const currentStepState = state.steps[state.currentStepIndex];
  const isFirstStep = state.currentStepIndex === 0;
  const isLastStep = state.currentStepIndex === steps.length - 1;

  // Step statuses for indicator
  const stepStatuses = useMemo(() => {
    return state.steps.map((stepState, index) => {
      if (index === state.currentStepIndex) return 'current' as StepStatus;
      return stepState.status;
    });
  }, [state.steps, state.currentStepIndex]);

  // Progress percentage
  const progressPercentage = useMemo(() => {
    const completedCount = state.steps.filter(
      (s) => s.status === 'completed' || s.status === 'skipped'
    ).length;
    return Math.round((completedCount / steps.length) * 100);
  }, [state.steps, steps.length]);

  // Update data for current step
  const updateData = useCallback(
    (field: string, value: unknown) => {
      setState((prev) => {
        const newSteps = [...prev.steps];
        newSteps[prev.currentStepIndex] = {
          ...newSteps[prev.currentStepIndex],
          data: {
            ...newSteps[prev.currentStepIndex].data,
            [field]: value,
          },
          touched: true,
        };
        return { ...prev, steps: newSteps };
      });
    },
    []
  );

  // Set errors for current step
  const setErrors = useCallback(
    (errors: Record<string, string>) => {
      setState((prev) => {
        const newSteps = [...prev.steps];
        newSteps[prev.currentStepIndex] = {
          ...newSteps[prev.currentStepIndex],
          errors,
          status: Object.keys(errors).length > 0 ? 'error' : newSteps[prev.currentStepIndex].status,
        };
        return { ...prev, steps: newSteps };
      });
    },
    []
  );

  // Notify on data change
  useEffect(() => {
    onDataChange?.(formData);
  }, [formData, onDataChange]);

  // Validate current step
  const validateCurrentStep = useCallback(async (): Promise<boolean> => {
    if (currentStep.validate) {
      try {
        const isValid = await currentStep.validate(formData);
        if (!isValid) {
          setState((prev) => {
            const newSteps = [...prev.steps];
            newSteps[prev.currentStepIndex] = {
              ...newSteps[prev.currentStepIndex],
              status: 'error',
            };
            return { ...prev, steps: newSteps };
          });
          return false;
        }
      } catch {
        return false;
      }
    }
    return true;
  }, [currentStep, formData]);

  // Go to next step
  const goNext = useCallback(async () => {
    if (isLastStep) return;

    const isValid = await validateCurrentStep();
    if (!isValid) return;

    setState((prev) => {
      const newSteps = [...prev.steps];
      newSteps[prev.currentStepIndex] = {
        ...newSteps[prev.currentStepIndex],
        status: 'completed',
      };
      return {
        ...prev,
        steps: newSteps,
        currentStepIndex: prev.currentStepIndex + 1,
      };
    });

    onStepChange?.(state.currentStepIndex + 1, 'next');
  }, [isLastStep, validateCurrentStep, state.currentStepIndex, onStepChange]);

  // Go to previous step
  const goPrev = useCallback(() => {
    if (isFirstStep) return;

    setState((prev) => ({
      ...prev,
      currentStepIndex: prev.currentStepIndex - 1,
    }));

    onStepChange?.(state.currentStepIndex - 1, 'prev');
  }, [isFirstStep, state.currentStepIndex, onStepChange]);

  // Go to specific step (from indicator)
  const goToStep = useCallback(
    (index: number) => {
      if (index < 0 || index >= steps.length) return;
      if (index > state.currentStepIndex) return; // Can only go back

      setState((prev) => ({
        ...prev,
        currentStepIndex: index,
      }));
    },
    [steps.length, state.currentStepIndex]
  );

  // Skip current step (if optional)
  const skipStep = useCallback(() => {
    if (!currentStep.optional || isLastStep) return;

    setState((prev) => {
      const newSteps = [...prev.steps];
      newSteps[prev.currentStepIndex] = {
        ...newSteps[prev.currentStepIndex],
        status: 'skipped',
      };
      return {
        ...prev,
        steps: newSteps,
        currentStepIndex: prev.currentStepIndex + 1,
      };
    });
  }, [currentStep.optional, isLastStep]);

  // Submit form
  const handleSubmit = useCallback(async () => {
    const isValid = await validateCurrentStep();
    if (!isValid) return;

    setState((prev) => ({ ...prev, isSubmitting: true }));

    try {
      await onSubmit(formData);
      setState((prev) => {
        const newSteps = [...prev.steps];
        newSteps[prev.currentStepIndex] = {
          ...newSteps[prev.currentStepIndex],
          status: 'completed',
        };
        return {
          ...prev,
          steps: newSteps,
          isSubmitting: false,
          isComplete: true,
        };
      });
    } catch {
      setState((prev) => ({ ...prev, isSubmitting: false }));
    }
  }, [validateCurrentStep, onSubmit, formData]);

  return (
    <div
      className={cn(
        'flex',
        indicatorPosition === 'left' ? 'flex-row gap-8' : 'flex-col gap-6',
        className
      )}
    >
      {/* Step Indicator */}
      {showIndicator && (
        <div className={cn(indicatorPosition === 'left' && 'w-64 flex-shrink-0')}>
          <StepIndicator
            steps={steps}
            currentStep={state.currentStepIndex}
            stepStatuses={stepStatuses}
            onStepClick={allowStepNavigation ? goToStep : undefined}
            allowNavigation={allowStepNavigation}
            orientation={indicatorPosition === 'left' ? 'vertical' : 'horizontal'}
          />
        </div>
      )}

      {/* Form Content */}
      <div className="flex-1">
        {/* Progress Bar */}
        {showProgress && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm text-slate-muted mb-1">
              <span>Progress</span>
              <span>{progressPercentage}%</span>
            </div>
            <div className="h-2 bg-slate-elevated rounded-full overflow-hidden">
              <div
                className="h-full bg-teal-electric transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        )}

        {/* Step Content */}
        <div className={cn('min-h-[200px]', contentClassName)}>
          {!state.isComplete ? (
            renderStep(
              currentStep,
              state.currentStepIndex,
              formData,
              updateData,
              currentStepState.errors,
              setErrors
            )
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4">
                <Check className="w-8 h-8 text-emerald-500" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-1">Complete!</h3>
              <p className="text-sm text-slate-muted">Form submitted successfully.</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        {!hideNavigation && !state.isComplete && (
          <div
            className={cn(
              'flex items-center justify-between pt-6 border-t border-slate-border mt-6',
              navigationClassName
            )}
          >
            <button
              type="button"
              onClick={goPrev}
              disabled={isFirstStep}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                isFirstStep
                  ? 'text-slate-muted cursor-not-allowed'
                  : 'text-foreground hover:bg-slate-elevated'
              )}
            >
              <ChevronLeft className="w-4 h-4" />
              {prevButtonLabel}
            </button>

            <div className="flex items-center gap-3">
              {/* Skip button for optional steps */}
              {currentStep.optional && !isLastStep && (
                <button
                  type="button"
                  onClick={skipStep}
                  className="px-4 py-2 text-sm text-slate-muted hover:text-foreground transition-colors"
                >
                  Skip
                </button>
              )}

              {/* Next / Submit button */}
              {isLastStep ? (
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={state.isSubmitting}
                  className={cn(
                    'flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-medium transition-colors',
                    'bg-teal-electric text-foreground hover:bg-teal-glow',
                    state.isSubmitting && 'opacity-60 cursor-not-allowed'
                  )}
                >
                  {state.isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      {submitButtonLabel}
                    </>
                  )}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={goNext}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    'bg-teal-electric text-foreground hover:bg-teal-glow'
                  )}
                >
                  {nextButtonLabel}
                  <ChevronRight className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default MultiStepForm;
