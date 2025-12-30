/**
 * MultiStepForm Component Tests
 *
 * Tests for multi-step form functionality including:
 * - Step navigation
 * - Form data management
 * - Validation
 * - Step indicator
 * - Skip/Optional steps
 * - Submit handling
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MultiStepForm } from './MultiStepForm';
import { StepIndicator } from './StepIndicator';
import type { FormStep, StepStatus } from './types';

// =============================================================================
// Mock Data
// =============================================================================

const mockSteps: FormStep[] = [
  {
    id: 'personal',
    title: 'Personal Info',
    description: 'Enter your details',
    fields: ['name', 'email'],
  },
  {
    id: 'address',
    title: 'Address',
    description: 'Where do you live?',
    optional: true,
    fields: ['street', 'city'],
  },
  {
    id: 'preferences',
    title: 'Preferences',
    description: 'Your preferences',
    fields: ['newsletter'],
  },
];

const renderStepContent = (
  step: FormStep,
  stepIndex: number,
  data: Record<string, unknown>,
  updateData: (field: string, value: unknown) => void,
  errors: Record<string, string>
) => (
  <div data-testid={`step-${step.id}`}>
    <h2>{step.title}</h2>
    <p>{step.description}</p>
    {step.fields?.map((field) => (
      <div key={field}>
        <input
          data-testid={`input-${field}`}
          value={(data[field] as string) || ''}
          onChange={(e) => updateData(field, e.target.value)}
          aria-invalid={!!errors[field]}
        />
        {errors[field] && (
          <span data-testid={`error-${field}`}>{errors[field]}</span>
        )}
      </div>
    ))}
  </div>
);

// =============================================================================
// MultiStepForm Tests
// =============================================================================

describe('MultiStepForm', () => {
  let onSubmit: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSubmit = vi.fn().mockResolvedValue(undefined);
  });

  describe('Rendering', () => {
    it('renders the first step by default', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      expect(screen.getByTestId('step-personal')).toBeInTheDocument();
      expect(screen.getByText('Personal Info')).toBeInTheDocument();
    });

    it('renders step indicator by default', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // All step titles should be visible in indicator
      mockSteps.forEach((step) => {
        expect(screen.getAllByText(step.title).length).toBeGreaterThan(0);
      });
    });

    it('hides step indicator when showIndicator is false', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          showIndicator={false}
        />
      );

      // Only step content title should be visible, not indicator titles
      expect(screen.getByText('Personal Info')).toBeInTheDocument();
      // Step indicator would have multiple instances of each title
      expect(screen.queryAllByText('Address').length).toBeLessThanOrEqual(1);
    });

    it('renders navigation buttons', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      expect(screen.getByText('Back')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
    });

    it('hides navigation when hideNavigation is true', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          hideNavigation={true}
        />
      );

      expect(screen.queryByText('Back')).not.toBeInTheDocument();
      expect(screen.queryByText('Next')).not.toBeInTheDocument();
    });

    it('shows progress bar when showProgress is true', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          showProgress={true}
        />
      );

      expect(screen.getByText('Progress')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('disables back button on first step', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      const backButton = screen.getByText('Back').closest('button');
      expect(backButton).toBeDisabled();
    });

    it('navigates to next step when Next is clicked', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      await user.click(screen.getByText('Next'));

      expect(screen.getByTestId('step-address')).toBeInTheDocument();
    });

    it('navigates back when Back is clicked', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Go to second step
      await user.click(screen.getByText('Next'));
      expect(screen.getByTestId('step-address')).toBeInTheDocument();

      // Go back
      await user.click(screen.getByText('Back'));
      expect(screen.getByTestId('step-personal')).toBeInTheDocument();
    });

    it('calls onStepChange when navigating', async () => {
      const onStepChange = vi.fn();
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          onStepChange={onStepChange}
        />
      );

      await user.click(screen.getByText('Next'));

      expect(onStepChange).toHaveBeenCalledWith(1, 'next');
    });

    it('shows Submit button on last step', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to last step
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));

      expect(screen.getByText('Submit')).toBeInTheDocument();
      expect(screen.queryByText('Next')).not.toBeInTheDocument();
    });
  });

  describe('Form Data', () => {
    it('updates data when input changes', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      const nameInput = screen.getByTestId('input-name');
      await user.type(nameInput, 'John Doe');

      expect(nameInput).toHaveValue('John Doe');
    });

    it('preserves data when navigating between steps', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Fill in first step
      await user.type(screen.getByTestId('input-name'), 'John');
      await user.type(screen.getByTestId('input-email'), 'john@example.com');

      // Go to next step
      await user.click(screen.getByText('Next'));
      expect(screen.getByTestId('step-address')).toBeInTheDocument();

      // Go back
      await user.click(screen.getByText('Back'));

      // Data should be preserved
      expect(screen.getByTestId('input-name')).toHaveValue('John');
      expect(screen.getByTestId('input-email')).toHaveValue('john@example.com');
    });

    it('calls onDataChange when data updates', async () => {
      const onDataChange = vi.fn();
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          onDataChange={onDataChange}
        />
      );

      await user.type(screen.getByTestId('input-name'), 'A');

      expect(onDataChange).toHaveBeenCalled();
    });

    it('includes initial data in form', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          initialData={{ name: 'Initial Name' }}
        />
      );

      expect(screen.getByTestId('input-name')).toHaveValue('Initial Name');
    });
  });

  describe('Validation', () => {
    it('calls step validation before proceeding', async () => {
      const validate = vi.fn().mockResolvedValue(true);
      const stepsWithValidation = [
        { ...mockSteps[0], validate },
        ...mockSteps.slice(1),
      ];
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={stepsWithValidation}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      await user.click(screen.getByText('Next'));

      expect(validate).toHaveBeenCalled();
    });

    it('prevents navigation when validation fails', async () => {
      const validate = vi.fn().mockResolvedValue(false);
      const stepsWithValidation = [
        { ...mockSteps[0], validate },
        ...mockSteps.slice(1),
      ];
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={stepsWithValidation}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      await user.click(screen.getByText('Next'));

      // Should still be on first step
      expect(screen.getByTestId('step-personal')).toBeInTheDocument();
    });

    it('validates before submit', async () => {
      const validate = vi.fn().mockResolvedValue(true);
      const stepsWithValidation = [
        mockSteps[0],
        mockSteps[1],
        { ...mockSteps[2], validate },
      ];
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={stepsWithValidation}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to last step
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Submit'));

      expect(validate).toHaveBeenCalled();
    });
  });

  describe('Optional Steps', () => {
    it('shows Skip button for optional steps', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to optional step
      await user.click(screen.getByText('Next'));

      expect(screen.getByText('Skip')).toBeInTheDocument();
    });

    it('does not show Skip button for required steps', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      expect(screen.queryByText('Skip')).not.toBeInTheDocument();
    });

    it('skips to next step when Skip is clicked', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to optional step
      await user.click(screen.getByText('Next'));
      expect(screen.getByTestId('step-address')).toBeInTheDocument();

      // Skip
      await user.click(screen.getByText('Skip'));

      expect(screen.getByTestId('step-preferences')).toBeInTheDocument();
    });

    it('marks step as skipped when skipped', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          showProgress={true}
        />
      );

      // Navigate to optional step and skip
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Skip'));

      // Progress should include skipped step
      // 2 steps done (completed + skipped) out of 3 = 67%
      expect(screen.getByText('67%')).toBeInTheDocument();
    });
  });

  describe('Submit', () => {
    it('calls onSubmit with form data', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Fill in data
      await user.type(screen.getByTestId('input-name'), 'John');

      // Navigate to last step and submit
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Submit'));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'John' })
        );
      });
    });

    it('shows loading state during submit', async () => {
      onSubmit.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to last step
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Submit'));

      expect(screen.getByText('Submitting...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Submitting...')).not.toBeInTheDocument();
      });
    });

    it('shows completion message after successful submit', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to last step and submit
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Submit'));

      await waitFor(() => {
        expect(screen.getByText('Complete!')).toBeInTheDocument();
        expect(screen.getByText('Form submitted successfully.')).toBeInTheDocument();
      });
    });

    it('hides navigation after completion', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Navigate to last step and submit
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Submit'));

      await waitFor(() => {
        expect(screen.getByText('Complete!')).toBeInTheDocument();
      });

      expect(screen.queryByText('Back')).not.toBeInTheDocument();
      expect(screen.queryByText('Submit')).not.toBeInTheDocument();
    });
  });

  describe('Custom Labels', () => {
    it('uses custom button labels', () => {
      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          nextButtonLabel="Continue"
          prevButtonLabel="Previous"
        />
      );

      expect(screen.getByText('Continue')).toBeInTheDocument();
      expect(screen.getByText('Previous')).toBeInTheDocument();
    });

    it('uses custom submit label', async () => {
      const user = userEvent.setup();

      render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          submitButtonLabel="Finish"
        />
      );

      // Navigate to last step
      await user.click(screen.getByText('Next'));
      await user.click(screen.getByText('Next'));

      expect(screen.getByText('Finish')).toBeInTheDocument();
    });
  });

  describe('Indicator Position', () => {
    it('renders indicator on top by default', () => {
      const { container } = render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
        />
      );

      // Check flex direction is column
      expect(container.firstChild).toHaveClass('flex-col');
    });

    it('renders indicator on left when specified', () => {
      const { container } = render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          indicatorPosition="left"
        />
      );

      // Check flex direction is row
      expect(container.firstChild).toHaveClass('flex-row');
    });
  });

  describe('CSS Classes', () => {
    it('applies custom className', () => {
      const { container } = render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          className="custom-form"
        />
      );

      expect(container.querySelector('.custom-form')).toBeInTheDocument();
    });

    it('applies contentClassName', () => {
      const { container } = render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          contentClassName="custom-content"
        />
      );

      expect(container.querySelector('.custom-content')).toBeInTheDocument();
    });

    it('applies navigationClassName', () => {
      const { container } = render(
        <MultiStepForm
          steps={mockSteps}
          onSubmit={onSubmit}
          renderStep={renderStepContent}
          navigationClassName="custom-nav"
        />
      );

      expect(container.querySelector('.custom-nav')).toBeInTheDocument();
    });
  });
});

// =============================================================================
// StepIndicator Tests
// =============================================================================

describe('StepIndicator', () => {
  const defaultProps = {
    steps: mockSteps,
    currentStep: 0,
    stepStatuses: ['current', 'pending', 'pending'] as StepStatus[],
    allowNavigation: true,
  };

  it('renders all steps', () => {
    render(<StepIndicator {...defaultProps} />);

    mockSteps.forEach((step) => {
      expect(screen.getByText(step.title)).toBeInTheDocument();
    });
  });

  it('shows step numbers by default', () => {
    render(<StepIndicator {...defaultProps} />);

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('hides step numbers when showNumbers is false', () => {
    render(<StepIndicator {...defaultProps} showNumbers={false} />);

    expect(screen.queryByText('1')).not.toBeInTheDocument();
    expect(screen.queryByText('2')).not.toBeInTheDocument();
  });

  it('shows step descriptions', () => {
    render(<StepIndicator {...defaultProps} />);

    expect(screen.getByText('Enter your details')).toBeInTheDocument();
    expect(screen.getByText('Where do you live?')).toBeInTheDocument();
  });

  it('marks optional steps', () => {
    render(<StepIndicator {...defaultProps} />);

    expect(screen.getByText('(optional)')).toBeInTheDocument();
  });

  it('highlights current step', () => {
    const { container } = render(<StepIndicator {...defaultProps} />);

    // Current step should have teal background
    const currentStepButton = container.querySelector('.bg-teal-electric');
    expect(currentStepButton).toBeInTheDocument();
  });

  it('shows checkmark for completed steps', () => {
    const { container } = render(
      <StepIndicator
        {...defaultProps}
        currentStep={1}
        stepStatuses={['completed', 'current', 'pending']}
      />
    );

    // First step should have check icon (svg)
    const firstStepCircle = container.querySelector('.bg-emerald-500');
    expect(firstStepCircle).toBeInTheDocument();
  });

  it('calls onStepClick when step is clicked', async () => {
    const onStepClick = vi.fn();
    const user = userEvent.setup();

    render(
      <StepIndicator
        {...defaultProps}
        currentStep={1}
        stepStatuses={['completed', 'current', 'pending']}
        onStepClick={onStepClick}
      />
    );

    // Click on first (completed) step
    const buttons = screen.getAllByRole('button');
    await user.click(buttons[0]);

    expect(onStepClick).toHaveBeenCalledWith(0);
  });

  it('does not call onStepClick for pending steps', async () => {
    const onStepClick = vi.fn();
    const user = userEvent.setup();

    render(
      <StepIndicator
        {...defaultProps}
        onStepClick={onStepClick}
      />
    );

    // Try to click on pending step (step 2)
    const buttons = screen.getAllByRole('button');
    await user.click(buttons[1]);

    expect(onStepClick).not.toHaveBeenCalled();
  });

  it('does not call onStepClick when allowNavigation is false', async () => {
    const onStepClick = vi.fn();
    const user = userEvent.setup();

    render(
      <StepIndicator
        {...defaultProps}
        currentStep={1}
        stepStatuses={['completed', 'current', 'pending']}
        onStepClick={onStepClick}
        allowNavigation={false}
      />
    );

    const buttons = screen.getAllByRole('button');
    await user.click(buttons[0]);

    expect(onStepClick).not.toHaveBeenCalled();
  });

  describe('Orientation', () => {
    it('renders horizontally by default', () => {
      const { container } = render(<StepIndicator {...defaultProps} />);

      expect(container.firstChild).toHaveClass('flex-row');
    });

    it('renders vertically when specified', () => {
      const { container } = render(
        <StepIndicator {...defaultProps} orientation="vertical" />
      );

      expect(container.firstChild).toHaveClass('flex-col');
    });
  });

  describe('Step Statuses', () => {
    it('shows error styling for error status', () => {
      const { container } = render(
        <StepIndicator
          {...defaultProps}
          stepStatuses={['error', 'pending', 'pending']}
        />
      );

      const errorStep = container.querySelector('.text-coral-alert');
      expect(errorStep).toBeInTheDocument();
    });

    it('shows skipped styling for skipped status', () => {
      const { container } = render(
        <StepIndicator
          {...defaultProps}
          currentStep={2}
          stepStatuses={['completed', 'skipped', 'current']}
        />
      );

      // Skipped step should have slate styling
      const skippedText = screen.getAllByText('Address')[0];
      expect(skippedText).toHaveClass('text-slate-muted');
    });
  });
});

// =============================================================================
// Integration Tests
// =============================================================================

describe('MultiStepForm Integration', () => {
  it('completes full form flow', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <MultiStepForm
        steps={mockSteps}
        onSubmit={onSubmit}
        renderStep={renderStepContent}
        showProgress={true}
      />
    );

    // Step 1: Fill personal info
    await user.type(screen.getByTestId('input-name'), 'John Doe');
    await user.type(screen.getByTestId('input-email'), 'john@example.com');
    await user.click(screen.getByText('Next'));

    // Step 2: Skip address (optional)
    await user.click(screen.getByText('Skip'));

    // Step 3: Fill preferences and submit
    await user.type(screen.getByTestId('input-newsletter'), 'yes');
    await user.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'John Doe',
          email: 'john@example.com',
          newsletter: 'yes',
        })
      );
    });

    expect(screen.getByText('Complete!')).toBeInTheDocument();
  });

  it('handles validation errors in flow', async () => {
    const validate = vi.fn().mockResolvedValue(false);
    const stepsWithValidation = [
      { ...mockSteps[0], validate },
      ...mockSteps.slice(1),
    ];
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <MultiStepForm
        steps={stepsWithValidation}
        onSubmit={onSubmit}
        renderStep={renderStepContent}
      />
    );

    // Try to proceed without valid data
    await user.click(screen.getByText('Next'));

    // Should stay on first step
    expect(screen.getByTestId('step-personal')).toBeInTheDocument();

    // Now pass validation
    validate.mockResolvedValue(true);
    await user.click(screen.getByText('Next'));

    // Should move to second step
    expect(screen.getByTestId('step-address')).toBeInTheDocument();
  });

  it('allows navigating back through indicator', async () => {
    const user = userEvent.setup();

    render(
      <MultiStepForm
        steps={mockSteps}
        onSubmit={vi.fn()}
        renderStep={renderStepContent}
        allowStepNavigation={true}
      />
    );

    // Navigate forward
    await user.click(screen.getByText('Next'));
    await user.click(screen.getByText('Next'));
    expect(screen.getByTestId('step-preferences')).toBeInTheDocument();

    // Click on first step in indicator
    const stepButtons = screen.getAllByRole('button');
    // Find the step 1 button (should be the one with "1" text)
    const step1Button = stepButtons.find((btn) =>
      btn.textContent?.includes('1') || btn.querySelector('svg')
    );

    if (step1Button) {
      await user.click(step1Button);
    }

    // Should go back to first step
    expect(screen.getByTestId('step-personal')).toBeInTheDocument();
  });
});
