// =============================================================================
// MULTI-STEP FORM TYPES
// =============================================================================

export interface FormStep {
  /** Unique step ID */
  id: string;
  /** Step title */
  title: string;
  /** Optional description */
  description?: string;
  /** Optional icon name */
  icon?: string;
  /** Whether step is optional */
  optional?: boolean;
  /** Custom validation function */
  validate?: (data: Record<string, unknown>) => Promise<boolean> | boolean;
  /** Fields in this step (for progress tracking) */
  fields?: string[];
}

export type StepStatus = 'pending' | 'current' | 'completed' | 'error' | 'skipped';

export interface StepState {
  id: string;
  status: StepStatus;
  data: Record<string, unknown>;
  errors: Record<string, string>;
  touched: boolean;
}

export interface MultiStepFormState {
  currentStepIndex: number;
  steps: StepState[];
  isSubmitting: boolean;
  isComplete: boolean;
}
