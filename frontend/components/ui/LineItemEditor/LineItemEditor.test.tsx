/**
 * LineItemEditor Component Tests
 *
 * Tests for line item editor functionality including:
 * - Row rendering
 * - Adding/deleting rows
 * - Cell editing
 * - Computed values
 * - Totals calculation
 * - Validation errors
 * - Drag and drop reordering
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LineItemEditor } from './LineItemEditor';
import { LineItemRow } from './LineItemRow';
import type { LineItemColumn, TotalConfig, LineItemValidation } from './types';

// =============================================================================
// Mock Data
// =============================================================================

interface TestItem {
  description: string;
  quantity: number;
  unitPrice: number;
  amount: number;
  taxable: boolean;
}

const mockItems: TestItem[] = [
  { description: 'Widget A', quantity: 2, unitPrice: 50, amount: 100, taxable: true },
  { description: 'Widget B', quantity: 3, unitPrice: 30, amount: 90, taxable: false },
  { description: 'Widget C', quantity: 1, unitPrice: 100, amount: 100, taxable: true },
];

const mockColumns: LineItemColumn<TestItem>[] = [
  {
    key: 'description',
    header: 'Description',
    type: 'text',
    required: true,
    width: '200px',
    placeholder: 'Enter description',
  },
  {
    key: 'quantity',
    header: 'Qty',
    type: 'number',
    align: 'right',
    min: 1,
    max: 100,
    width: '80px',
  },
  {
    key: 'unitPrice',
    header: 'Unit Price',
    type: 'currency',
    align: 'right',
    width: '120px',
  },
  {
    key: 'amount',
    header: 'Amount',
    type: 'readonly',
    align: 'right',
    width: '120px',
    compute: (row) => row.quantity * row.unitPrice,
    format: (value) => `$${(value as number).toFixed(2)}`,
  },
  {
    key: 'taxable',
    header: 'Tax',
    type: 'checkbox',
    align: 'center',
    width: '60px',
  },
];

const mockTotalsConfig: TotalConfig<TestItem>[] = [
  {
    key: 'amount',
    label: 'Total',
    format: (value) => `$${value.toFixed(2)}`,
  },
];

const createEmptyRow = (): TestItem => ({
  description: '',
  quantity: 1,
  unitPrice: 0,
  amount: 0,
  taxable: false,
});

// =============================================================================
// LineItemEditor Tests
// =============================================================================

describe('LineItemEditor', () => {
  let onChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onChange = vi.fn();
  });

  describe('Rendering', () => {
    it('renders column headers', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Qty')).toBeInTheDocument();
      expect(screen.getByText('Unit Price')).toBeInTheDocument();
      expect(screen.getByText('Amount')).toBeInTheDocument();
      expect(screen.getByText('Tax')).toBeInTheDocument();
    });

    it('renders all rows', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      expect(screen.getByDisplayValue('Widget A')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Widget B')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Widget C')).toBeInTheDocument();
    });

    it('shows row numbers by default', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('hides row numbers when showRowNumbers is false', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          showRowNumbers={false}
        />
      );

      // Row numbers column header (#) should not exist
      expect(screen.queryByText('#')).not.toBeInTheDocument();
    });

    it('shows required marker for required columns', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      // Description column has required: true
      const descHeader = screen.getByText('Description');
      const headerCell = descHeader.closest('th');
      expect(headerCell?.textContent).toContain('*');
    });

    it('shows empty state when no items', () => {
      render(
        <LineItemEditor
          items={[]}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      expect(screen.getByText('No items. Click "Add Row" to start.')).toBeInTheDocument();
    });

    it('shows custom empty message', () => {
      render(
        <LineItemEditor
          items={[]}
          onChange={onChange}
          columns={mockColumns}
          emptyMessage="Add your first line item"
        />
      );

      expect(screen.getByText('Add your first line item')).toBeInTheDocument();
    });
  });

  describe('Adding Rows', () => {
    it('shows add button by default', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      expect(screen.getByText('Add Row')).toBeInTheDocument();
    });

    it('uses custom add button label', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          addButtonLabel="Add Line Item"
        />
      );

      expect(screen.getByText('Add Line Item')).toBeInTheDocument();
    });

    it('adds new row when add button clicked', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          createRow={createEmptyRow}
        />
      );

      await user.click(screen.getByText('Add Row'));

      expect(onChange).toHaveBeenCalledWith([
        ...mockItems,
        createEmptyRow(),
      ]);
    });

    it('respects maxRows limit', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          maxRows={3}
        />
      );

      // Should not be able to add more (already at max)
      const addButton = screen.queryByText('Add Row');
      expect(addButton).not.toBeInTheDocument();
    });

    it('hides add button in read-only mode', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          readOnly={true}
        />
      );

      expect(screen.queryByText('Add Row')).not.toBeInTheDocument();
    });
  });

  describe('Deleting Rows', () => {
    it('shows delete button for each row', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      // Each row should have a delete button
      const deleteButtons = container.querySelectorAll('button[title="Delete row"]');
      expect(deleteButtons.length).toBe(3);
    });

    it('deletes row when delete button clicked', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      const deleteButtons = container.querySelectorAll('button[title="Delete row"]');
      await user.click(deleteButtons[0]);

      expect(onChange).toHaveBeenCalledWith([mockItems[1], mockItems[2]]);
    });

    it('calls onDeleteRow callback', async () => {
      const onDeleteRow = vi.fn();
      const user = userEvent.setup();

      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          onDeleteRow={onDeleteRow}
        />
      );

      const deleteButtons = container.querySelectorAll('button[title="Delete row"]');
      await user.click(deleteButtons[0]);

      expect(onDeleteRow).toHaveBeenCalledWith(0, mockItems[0]);
    });

    it('respects minRows limit', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          minRows={3}
        />
      );

      // Should not show delete buttons when at minimum
      const deleteButtons = container.querySelectorAll('button[title="Delete row"]');
      expect(deleteButtons.length).toBe(0);
    });

    it('hides delete buttons in read-only mode', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          readOnly={true}
        />
      );

      const deleteButtons = container.querySelectorAll('button[title="Delete row"]');
      expect(deleteButtons.length).toBe(0);
    });
  });

  describe('Cell Editing', () => {
    it('updates text field value', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      const input = screen.getByDisplayValue('Widget A');
      await user.clear(input);
      await user.type(input, 'New Widget');

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      expect(lastCall[0].description).toBe('New Widget');
    });

    it('updates number field value', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      const inputs = screen.getAllByRole('spinbutton');
      // First number input should be quantity for first row
      await user.clear(inputs[0]);
      await user.type(inputs[0], '5');

      expect(onChange).toHaveBeenCalled();
    });

    it('updates checkbox value', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      expect(lastCall[0].taxable).toBe(false);
    });

    it('does not allow editing in read-only mode', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          readOnly={true}
        />
      );

      // Text inputs should not be editable
      const inputs = screen.queryAllByRole('textbox');
      inputs.forEach((input) => {
        expect(input).not.toBeInTheDocument();
      });

      // Checkboxes should be disabled
      const checkboxes = screen.getAllByRole('checkbox');
      checkboxes.forEach((checkbox) => {
        expect(checkbox).toBeDisabled();
      });
    });
  });

  describe('Computed Values', () => {
    it('computes values when row changes', async () => {
      const user = userEvent.setup();

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
        />
      );

      // Change quantity
      const quantityInputs = screen.getAllByRole('spinbutton');
      await user.clear(quantityInputs[0]);
      await user.type(quantityInputs[0], '5');

      // Check that computed amount is updated
      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      // Amount = quantity * unitPrice = 5 * 50 = 250
      expect(lastCall[0].amount).toBe(250);
    });
  });

  describe('Totals', () => {
    it('shows totals row when showTotals is true', () => {
      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          showTotals={true}
          totalsConfig={mockTotalsConfig}
        />
      );

      // Total should be 100 + 90 + 100 = 290
      expect(screen.getByText('$290.00')).toBeInTheDocument();
    });

    it('does not show totals when no items', () => {
      render(
        <LineItemEditor
          items={[]}
          onChange={onChange}
          columns={mockColumns}
          showTotals={true}
          totalsConfig={mockTotalsConfig}
        />
      );

      expect(screen.queryByText('Total:')).not.toBeInTheDocument();
    });

    it('uses custom calculate function for totals', () => {
      const customTotalsConfig: TotalConfig<TestItem>[] = [
        {
          key: 'amount',
          label: 'Total',
          calculate: (rows) => rows.reduce((sum, r) => sum + r.amount, 0) * 1.1, // Add 10%
          format: (value) => `$${value.toFixed(2)}`,
        },
      ];

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          showTotals={true}
          totalsConfig={customTotalsConfig}
        />
      );

      // Total with 10% = 290 * 1.1 = 319
      expect(screen.getByText('$319.00')).toBeInTheDocument();
    });
  });

  describe('Validation Errors', () => {
    it('shows validation error summary', () => {
      const errors: LineItemValidation[] = [
        { rowIndex: 0, column: 'description', message: 'Description is required' },
        { rowIndex: 1, column: 'quantity', message: 'Quantity must be positive' },
      ];

      render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          errors={errors}
        />
      );

      expect(screen.getByText('Validation Errors')).toBeInTheDocument();
      expect(screen.getByText('Row 1, description: Description is required')).toBeInTheDocument();
      expect(screen.getByText('Row 2, quantity: Quantity must be positive')).toBeInTheDocument();
    });

    it('truncates error list when more than 5 errors', () => {
      const errors: LineItemValidation[] = Array.from({ length: 8 }, (_, i) => ({
        rowIndex: i,
        column: 'description',
        message: `Error ${i + 1}`,
      }));

      render(
        <LineItemEditor
          items={Array.from({ length: 8 }, createEmptyRow)}
          onChange={onChange}
          columns={mockColumns}
          errors={errors}
        />
      );

      expect(screen.getByText('...and 3 more errors')).toBeInTheDocument();
    });

    it('highlights cells with errors', () => {
      const errors: LineItemValidation[] = [
        { rowIndex: 0, column: 'description', message: 'Error' },
      ];

      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          errors={errors}
        />
      );

      // Cell should have error background
      const errorCell = container.querySelector('.bg-coral-alert\\/5');
      expect(errorCell).toBeInTheDocument();
    });
  });

  describe('Drag and Drop', () => {
    it('shows drag handles when allowReorder is true', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          allowReorder={true}
        />
      );

      const dragHandles = container.querySelectorAll('[draggable="true"]');
      expect(dragHandles.length).toBe(3);
    });

    it('does not show drag handles when allowReorder is false', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          allowReorder={false}
        />
      );

      const dragHandles = container.querySelectorAll('[draggable="true"]');
      expect(dragHandles.length).toBe(0);
    });

    it('does not show drag handles in read-only mode', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          allowReorder={true}
          readOnly={true}
        />
      );

      const dragHandles = container.querySelectorAll('[draggable="true"]');
      expect(dragHandles.length).toBe(0);
    });

    it('reorders rows on drag and drop', async () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          allowReorder={true}
        />
      );

      const dragHandles = container.querySelectorAll('[draggable="true"]');
      const rows = container.querySelectorAll('tbody tr');

      // Simulate drag from first to third row
      fireEvent.dragStart(dragHandles[0], {
        dataTransfer: { effectAllowed: 'move' },
      });

      fireEvent.dragOver(rows[2], {
        preventDefault: vi.fn(),
      });

      fireEvent.drop(rows[2], {
        preventDefault: vi.fn(),
      });

      expect(onChange).toHaveBeenCalled();
      const newOrder = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      expect(newOrder[0].description).toBe('Widget B');
      expect(newOrder[1].description).toBe('Widget C');
      expect(newOrder[2].description).toBe('Widget A');
    });
  });

  describe('CSS Classes', () => {
    it('applies custom className', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          className="custom-editor"
        />
      );

      expect(container.querySelector('.custom-editor')).toBeInTheDocument();
    });

    it('applies tableClassName', () => {
      const { container } = render(
        <LineItemEditor
          items={mockItems}
          onChange={onChange}
          columns={mockColumns}
          tableClassName="custom-table"
        />
      );

      expect(container.querySelector('.custom-table')).toBeInTheDocument();
    });
  });
});

// =============================================================================
// LineItemRow Tests
// =============================================================================

describe('LineItemRow', () => {
  const defaultColumn: LineItemColumn<TestItem> = {
    key: 'description',
    header: 'Description',
    type: 'text',
  };

  const defaultRow: TestItem = {
    description: 'Test',
    quantity: 1,
    unitPrice: 100,
    amount: 100,
    taxable: false,
  };

  describe('Text Cell', () => {
    it('renders text input', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={defaultColumn}
                value="Test Value"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByDisplayValue('Test Value')).toBeInTheDocument();
    });

    it('shows placeholder', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={{ ...defaultColumn, placeholder: 'Enter text' }}
                value=""
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument();
    });

    it('shows readonly text value', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={defaultColumn}
                value="Readonly Value"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
                readOnly={true}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByText('Readonly Value')).toBeInTheDocument();
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  describe('Number Cell', () => {
    const numberColumn: LineItemColumn<TestItem> = {
      key: 'quantity',
      header: 'Qty',
      type: 'number',
      min: 0,
      max: 100,
    };

    it('renders number input', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={numberColumn}
                value={5}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByRole('spinbutton')).toHaveValue(5);
    });

    it('applies min/max constraints', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={numberColumn}
                value={50}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      const input = screen.getByRole('spinbutton');
      expect(input).toHaveAttribute('min', '0');
      expect(input).toHaveAttribute('max', '100');
    });
  });

  describe('Select Cell', () => {
    const selectColumn: LineItemColumn<TestItem> = {
      key: 'description',
      header: 'Type',
      type: 'select',
      options: [
        { value: 'a', label: 'Option A' },
        { value: 'b', label: 'Option B' },
        { value: 'c', label: 'Option C' },
      ],
    };

    it('renders select with options', async () => {
      const user = userEvent.setup();

      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={selectColumn}
                value="a"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      // Should show selected option
      expect(screen.getByText('Option A')).toBeInTheDocument();

      // Click to open dropdown
      await user.click(screen.getByText('Option A'));

      // All options should be visible
      expect(screen.getByText('Option B')).toBeInTheDocument();
      expect(screen.getByText('Option C')).toBeInTheDocument();
    });

    it('calls onChange when option selected', async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();

      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={selectColumn}
                value="a"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={onChange}
              />
            </tr>
          </tbody>
        </table>
      );

      await user.click(screen.getByText('Option A'));
      await user.click(screen.getByText('Option B'));

      expect(onChange).toHaveBeenCalledWith('b');
    });
  });

  describe('Checkbox Cell', () => {
    const checkboxColumn: LineItemColumn<TestItem> = {
      key: 'taxable',
      header: 'Taxable',
      type: 'checkbox',
    };

    it('renders checkbox', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={checkboxColumn}
                value={true}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('toggles checkbox value', async () => {
      const onChange = vi.fn();
      const user = userEvent.setup();

      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={checkboxColumn}
                value={false}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={onChange}
              />
            </tr>
          </tbody>
        </table>
      );

      await user.click(screen.getByRole('checkbox'));

      expect(onChange).toHaveBeenCalledWith(true);
    });
  });

  describe('Date Cell', () => {
    const dateColumn: LineItemColumn<TestItem> = {
      key: 'description',
      header: 'Date',
      type: 'date',
    };

    it('renders date input', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={dateColumn}
                value="2024-06-15"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByDisplayValue('2024-06-15')).toBeInTheDocument();
    });
  });

  describe('Readonly Cell', () => {
    const readonlyColumn: LineItemColumn<TestItem> = {
      key: 'amount',
      header: 'Amount',
      type: 'readonly',
      format: (value) => `$${(value as number).toFixed(2)}`,
    };

    it('renders formatted value', () => {
      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={readonlyColumn}
                value={100}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByText('$100.00')).toBeInTheDocument();
    });
  });

  describe('Custom Render', () => {
    it('uses custom render function', () => {
      const customColumn: LineItemColumn<TestItem> = {
        key: 'description',
        header: 'Custom',
        type: 'text',
        render: (value) => <div data-testid="custom-render">Custom: {String(value)}</div>,
      };

      render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={customColumn}
                value="Test"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      expect(screen.getByTestId('custom-render')).toBeInTheDocument();
      expect(screen.getByText('Custom: Test')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('shows error styling', () => {
      const { container } = render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={defaultColumn}
                value="Test"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
                error="This field is required"
              />
            </tr>
          </tbody>
        </table>
      );

      // Cell should have error background
      const cell = container.querySelector('td');
      expect(cell).toHaveClass('bg-coral-alert/5');
    });

    it('shows error on input', () => {
      const { container } = render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={defaultColumn}
                value="Test"
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
                error="Error message"
              />
            </tr>
          </tbody>
        </table>
      );

      const input = screen.getByRole('textbox');
      expect(input).toHaveClass('border-coral-alert');
    });
  });

  describe('Alignment', () => {
    it('applies text alignment classes', () => {
      const rightAlignedColumn: LineItemColumn<TestItem> = {
        key: 'quantity',
        header: 'Qty',
        type: 'number',
        align: 'right',
      };

      const { container } = render(
        <table>
          <tbody>
            <tr>
              <LineItemRow
                column={rightAlignedColumn}
                value={5}
                row={defaultRow}
                rowIndex={0}
                allRows={[defaultRow]}
                onChange={vi.fn()}
              />
            </tr>
          </tbody>
        </table>
      );

      const cell = container.querySelector('td');
      expect(cell).toHaveClass('text-right');
    });
  });
});
