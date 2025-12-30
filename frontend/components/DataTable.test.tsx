/**
 * DataTable Component Tests
 *
 * Tests for the DataTable and Pagination components including:
 * - Rendering columns and data
 * - Sorting functionality
 * - Row selection
 * - Loading and empty states
 * - Pagination controls
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, userEvent, within } from '@/tests/utils/render';
import { DataTable, Pagination, Column } from './DataTable';

// =============================================================================
// TEST DATA
// =============================================================================

interface TestItem {
  id: number;
  name: string;
  email: string;
  status: string;
  amount: number;
}

const mockData: TestItem[] = [
  { id: 1, name: 'Alice Johnson', email: 'alice@test.com', status: 'active', amount: 1000 },
  { id: 2, name: 'Bob Smith', email: 'bob@test.com', status: 'inactive', amount: 2000 },
  { id: 3, name: 'Carol White', email: 'carol@test.com', status: 'active', amount: 1500 },
  { id: 4, name: 'David Brown', email: 'david@test.com', status: 'pending', amount: 3000 },
  { id: 5, name: 'Eve Davis', email: 'eve@test.com', status: 'active', amount: 500 },
];

const columns: Column<TestItem>[] = [
  { key: 'name', header: 'Name', sortable: true },
  { key: 'email', header: 'Email' },
  { key: 'status', header: 'Status', sortable: true },
  {
    key: 'amount',
    header: 'Amount',
    sortable: true,
    align: 'right',
    render: (item) => `$${item.amount.toLocaleString()}`,
  },
];

// =============================================================================
// DATATABLE TESTS
// =============================================================================

describe('DataTable', () => {
  describe('Basic Rendering', () => {
    it('renders column headers correctly', () => {
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Amount')).toBeInTheDocument();
    });

    it('renders all data rows', () => {
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
      expect(screen.getByText('Bob Smith')).toBeInTheDocument();
      expect(screen.getByText('Carol White')).toBeInTheDocument();
      expect(screen.getByText('David Brown')).toBeInTheDocument();
      expect(screen.getByText('Eve Davis')).toBeInTheDocument();
    });

    it('renders custom cell content via render prop', () => {
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      // Check formatted amount
      expect(screen.getByText('$1,000')).toBeInTheDocument();
      expect(screen.getByText('$2,000')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          className="custom-table-class"
        />
      );

      expect(container.firstChild).toHaveClass('custom-table-class');
    });
  });

  describe('Empty State', () => {
    it('shows default empty message when data is empty', () => {
      render(
        <DataTable columns={columns} data={[]} keyField="id" />
      );

      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('shows custom empty message when provided', () => {
      render(
        <DataTable
          columns={columns}
          data={[]}
          keyField="id"
          emptyMessage="No customers found"
        />
      );

      expect(screen.getByText('No customers found')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows skeleton loader when loading', () => {
      render(
        <DataTable columns={columns} data={[]} keyField="id" loading={true} />
      );

      // Should show skeleton rows
      const skeletons = document.querySelectorAll('.skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('renders column headers during loading', () => {
      render(
        <DataTable columns={columns} data={[]} keyField="id" loading={true} />
      );

      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Email')).toBeInTheDocument();
    });
  });

  describe('Sorting', () => {
    it('shows sort indicator on sortable columns', () => {
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      // Name column is sortable - should have sort icon
      const nameHeader = screen.getByText('Name').closest('th');
      expect(nameHeader).toHaveClass('cursor-pointer');
    });

    it('handles internal sorting when clicked', async () => {
      const user = userEvent.setup();
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      const nameHeader = screen.getByText('Name').closest('th')!;
      await user.click(nameHeader);

      // After sorting by name ascending, Alice should be first
      const rows = document.querySelectorAll('tbody tr');
      expect(within(rows[0] as HTMLElement).getByText('Alice Johnson')).toBeInTheDocument();
    });

    it('toggles sort direction on second click', async () => {
      const user = userEvent.setup();
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      const nameHeader = screen.getByText('Name').closest('th')!;
      
      // First click - ascending
      await user.click(nameHeader);
      
      // Second click - descending
      await user.click(nameHeader);

      // After sorting by name descending, Eve should be first
      const rows = document.querySelectorAll('tbody tr');
      expect(within(rows[0] as HTMLElement).getByText('Eve Davis')).toBeInTheDocument();
    });

    it('calls onSortChange when provided', async () => {
      const onSortChange = vi.fn();
      const user = userEvent.setup();

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          onSortChange={onSortChange}
        />
      );

      const nameHeader = screen.getByText('Name').closest('th')!;
      await user.click(nameHeader);

      expect(onSortChange).toHaveBeenCalledWith('name', 'asc');
    });

    it('respects controlled sort state', () => {
      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          sortKey="amount"
          sortDir="desc"
          manualSort={true}
        />
      );

      // Data should not be reordered when manualSort is true
      // The parent component handles sorting
    });
  });

  describe('Row Selection', () => {
    it('renders checkboxes when selectable is true', () => {
      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={{}}
          onSelectChange={vi.fn()}
        />
      );

      // Should have select all checkbox + one per row
      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes.length).toBe(mockData.length + 1);
    });

    it('handles individual row selection', async () => {
      const onSelectChange = vi.fn();
      const user = userEvent.setup();

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={{}}
          onSelectChange={onSelectChange}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      // First checkbox is "select all", second is first row
      await user.click(checkboxes[1]);

      expect(onSelectChange).toHaveBeenCalledWith({ '1': true });
    });

    it('handles select all checkbox', async () => {
      const onSelectChange = vi.fn();
      const user = userEvent.setup();

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={{}}
          onSelectChange={onSelectChange}
        />
      );

      const selectAllCheckbox = screen.getByLabelText('Select all rows');
      await user.click(selectAllCheckbox);

      // Should call with all row IDs selected
      expect(onSelectChange).toHaveBeenCalledWith({
        '1': true,
        '2': true,
        '3': true,
        '4': true,
        '5': true,
      });
    });

    it('shows checked state for selected rows', () => {
      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={{ '1': true, '3': true }}
          onSelectChange={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
      
      // Row 1 (index 1) and Row 3 (index 3) should be checked
      expect(checkboxes[1].checked).toBe(true);
      expect(checkboxes[2].checked).toBe(false);
      expect(checkboxes[3].checked).toBe(true);
    });

    it('supports Set for selectedRowIds', () => {
      const selectedSet = new Set(['1', '2']);

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={selectedSet}
          onSelectChange={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
      expect(checkboxes[1].checked).toBe(true);
      expect(checkboxes[2].checked).toBe(true);
      expect(checkboxes[3].checked).toBe(false);
    });
  });

  describe('Row Click', () => {
    it('calls onRowClick when row is clicked', async () => {
      const onRowClick = vi.fn();
      const user = userEvent.setup();

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          onRowClick={onRowClick}
        />
      );

      const firstRow = screen.getByText('Alice Johnson').closest('tr')!;
      await user.click(firstRow);

      expect(onRowClick).toHaveBeenCalledWith(mockData[0]);
    });

    it('applies cursor-pointer class when clickable', () => {
      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          onRowClick={vi.fn()}
        />
      );

      const firstRow = screen.getByText('Alice Johnson').closest('tr')!;
      expect(firstRow).toHaveClass('cursor-pointer');
    });

    it('does not propagate click from checkbox to row', async () => {
      const onRowClick = vi.fn();
      const onSelectChange = vi.fn();
      const user = userEvent.setup();

      render(
        <DataTable
          columns={columns}
          data={mockData}
          keyField="id"
          selectable={true}
          selectedRowIds={{}}
          onSelectChange={onSelectChange}
          onRowClick={onRowClick}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]);

      expect(onSelectChange).toHaveBeenCalled();
      expect(onRowClick).not.toHaveBeenCalled();
    });
  });

  describe('Column Alignment', () => {
    it('applies right alignment to amount column', () => {
      render(
        <DataTable columns={columns} data={mockData} keyField="id" />
      );

      // Amount header should have text-right class
      const amountHeader = screen.getByText('Amount').closest('th')!;
      expect(amountHeader).toHaveClass('text-right');
    });
  });
});

// =============================================================================
// PAGINATION TESTS
// =============================================================================

describe('Pagination', () => {
  const defaultProps = {
    total: 100,
    limit: 10,
    offset: 0,
    onPageChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('shows correct range text', () => {
      render(<Pagination {...defaultProps} />);

      expect(screen.getByText(/Showing 1 to 10 of 100/)).toBeInTheDocument();
    });

    it('shows correct range on middle page', () => {
      render(<Pagination {...defaultProps} offset={30} />);

      expect(screen.getByText(/Showing 31 to 40 of 100/)).toBeInTheDocument();
    });

    it('shows correct range on last page', () => {
      render(<Pagination {...defaultProps} offset={90} />);

      expect(screen.getByText(/Showing 91 to 100 of 100/)).toBeInTheDocument();
    });

    it('handles partial last page', () => {
      render(<Pagination {...defaultProps} total={95} offset={90} />);

      expect(screen.getByText(/Showing 91 to 95 of 95/)).toBeInTheDocument();
    });
  });

  describe('Navigation Buttons', () => {
    it('disables Previous button on first page', () => {
      render(<Pagination {...defaultProps} offset={0} />);

      const prevButton = screen.getByText('Previous');
      expect(prevButton).toBeDisabled();
    });

    it('disables Next button on last page', () => {
      render(<Pagination {...defaultProps} offset={90} />);

      const nextButton = screen.getByText('Next');
      expect(nextButton).toBeDisabled();
    });

    it('calls onPageChange when Previous is clicked', async () => {
      const onPageChange = vi.fn();
      const user = userEvent.setup();

      render(<Pagination {...defaultProps} offset={20} onPageChange={onPageChange} />);

      await user.click(screen.getByText('Previous'));

      expect(onPageChange).toHaveBeenCalledWith(10);
    });

    it('calls onPageChange when Next is clicked', async () => {
      const onPageChange = vi.fn();
      const user = userEvent.setup();

      render(<Pagination {...defaultProps} offset={20} onPageChange={onPageChange} />);

      await user.click(screen.getByText('Next'));

      expect(onPageChange).toHaveBeenCalledWith(30);
    });
  });

  describe('Page Number Buttons', () => {
    it('renders page number buttons', () => {
      render(<Pagination {...defaultProps} />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('highlights current page', () => {
      render(<Pagination {...defaultProps} offset={20} />);

      const page3Button = screen.getByText('3');
      expect(page3Button).toHaveClass('bg-teal-electric/20');
    });

    it('calls onPageChange when page number is clicked', async () => {
      const onPageChange = vi.fn();
      const user = userEvent.setup();

      render(<Pagination {...defaultProps} onPageChange={onPageChange} />);

      await user.click(screen.getByText('3'));

      expect(onPageChange).toHaveBeenCalledWith(20);
    });

    it('shows ellipsis for many pages', () => {
      render(<Pagination {...defaultProps} offset={40} />);

      // Should show ellipsis indicators
      const ellipses = screen.getAllByText('...');
      expect(ellipses.length).toBeGreaterThan(0);
    });

    it('shows all pages when total pages <= 7', () => {
      render(<Pagination total={50} limit={10} offset={0} onPageChange={vi.fn()} />);

      // 5 pages total - should show all
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.queryByText('...')).not.toBeInTheDocument();
    });
  });

  describe('Per Page Select', () => {
    it('shows per page select when onLimitChange is provided', () => {
      render(
        <Pagination
          {...defaultProps}
          onLimitChange={vi.fn()}
        />
      );

      expect(screen.getByText('Per page:')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('does not show per page select when onLimitChange is not provided', () => {
      render(<Pagination {...defaultProps} />);

      expect(screen.queryByText('Per page:')).not.toBeInTheDocument();
    });

    it('calls onLimitChange when select value changes', async () => {
      const onLimitChange = vi.fn();
      const onPageChange = vi.fn();
      const user = userEvent.setup();

      render(
        <Pagination
          {...defaultProps}
          onLimitChange={onLimitChange}
          onPageChange={onPageChange}
        />
      );

      const select = screen.getByRole('combobox');
      await user.selectOptions(select, '50');

      expect(onLimitChange).toHaveBeenCalledWith(50);
      expect(onPageChange).toHaveBeenCalledWith(0); // Reset to first page
    });

    it('renders custom limit options', () => {
      render(
        <Pagination
          {...defaultProps}
          onLimitChange={vi.fn()}
          limitOptions={[10, 25, 50, 100]}
        />
      );

      const select = screen.getByRole('combobox');
      expect(within(select).getByText('10')).toBeInTheDocument();
      expect(within(select).getByText('25')).toBeInTheDocument();
      expect(within(select).getByText('50')).toBeInTheDocument();
      expect(within(select).getByText('100')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles single page result', () => {
      render(
        <Pagination total={5} limit={10} offset={0} onPageChange={vi.fn()} />
      );

      // Should show range but no page buttons
      expect(screen.getByText(/Showing 1 to 5 of 5/)).toBeInTheDocument();
      // Previous/Next should not be visible for single page
    });

    it('handles zero results', () => {
      render(
        <Pagination total={0} limit={10} offset={0} onPageChange={vi.fn()} />
      );

      expect(screen.getByText(/Showing 1 to 0 of 0/)).toBeInTheDocument();
    });
  });
});
