/**
 * KanbanBoard Component Tests
 *
 * Tests for Kanban board functionality including:
 * - Column rendering
 * - Item rendering
 * - Drag and drop
 * - Loading states
 * - Empty states
 * - Custom renderers
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { KanbanBoard } from './KanbanBoard';
import { KanbanColumn } from './KanbanColumn';
import { KanbanCard, OpportunityCard, TaskCard } from './KanbanCard';
import { getColumnColors, KANBAN_COLORS } from './types';
import type { KanbanItem, KanbanColumn as KanbanColumnType, DragResult } from './types';

// =============================================================================
// Mock Data
// =============================================================================

interface TestItem extends KanbanItem {
  id: number;
  title: string;
  value?: number;
}

const mockItems: TestItem[] = [
  { id: 1, title: 'Task 1', value: 100 },
  { id: 2, title: 'Task 2', value: 200 },
  { id: 3, title: 'Task 3', value: 300 },
];

const mockColumns: KanbanColumnType<TestItem>[] = [
  {
    id: 'todo',
    title: 'To Do',
    items: [mockItems[0], mockItems[1]],
    color: 'blue',
  },
  {
    id: 'in-progress',
    title: 'In Progress',
    items: [mockItems[2]],
    color: 'amber',
  },
  {
    id: 'done',
    title: 'Done',
    items: [],
    color: 'green',
  },
];

// Default render function for items
const renderItem = (item: TestItem) => (
  <div data-testid={`item-${item.id}`}>
    <span>{item.title}</span>
    {item.value && <span>${item.value}</span>}
  </div>
);

// =============================================================================
// KanbanBoard Tests
// =============================================================================

describe('KanbanBoard', () => {
  let onMoveItem: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onMoveItem = vi.fn().mockResolvedValue(undefined);
  });

  describe('Rendering', () => {
    it('renders all columns', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      expect(screen.getByText('To Do')).toBeInTheDocument();
      expect(screen.getByText('In Progress')).toBeInTheDocument();
      expect(screen.getByText('Done')).toBeInTheDocument();
    });

    it('renders items in correct columns', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      expect(screen.getByTestId('item-1')).toBeInTheDocument();
      expect(screen.getByTestId('item-2')).toBeInTheDocument();
      expect(screen.getByTestId('item-3')).toBeInTheDocument();
    });

    it('shows item count in column headers', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      // Column counts are shown in the default header
      expect(screen.getByText('2')).toBeInTheDocument(); // To Do has 2 items
      expect(screen.getByText('1')).toBeInTheDocument(); // In Progress has 1 item
      expect(screen.getByText('0')).toBeInTheDocument(); // Done has 0 items
    });

    it('shows empty state for columns with no items', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      expect(screen.getByText('No items')).toBeInTheDocument();
      expect(screen.getByText('Drag items here')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when loading', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          loading={true}
        />
      );

      // Should show 4 skeleton columns with animation
      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThanOrEqual(4);
    });

    it('does not render columns when loading', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          loading={true}
        />
      );

      expect(screen.queryByText('To Do')).not.toBeInTheDocument();
      expect(screen.queryByText('In Progress')).not.toBeInTheDocument();
    });
  });

  describe('Add Button', () => {
    it('shows add button by default', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      const addButtons = screen.getAllByText('Add Item');
      expect(addButtons.length).toBe(3); // One per column
    });

    it('hides add button when showAddButton is false', () => {
      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          showAddButton={false}
        />
      );

      expect(screen.queryByText('Add Item')).not.toBeInTheDocument();
    });

    it('respects column allowAdd property', () => {
      const columnsWithRestrictions = [
        { ...mockColumns[0], allowAdd: true },
        { ...mockColumns[1], allowAdd: false },
        { ...mockColumns[2], allowAdd: true },
      ];

      render(
        <KanbanBoard
          columns={columnsWithRestrictions}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      const addButtons = screen.getAllByText('Add Item');
      expect(addButtons.length).toBe(2); // Only 2 columns allow adding
    });

    it('calls onAddItem with column id when clicked', async () => {
      const onAddItem = vi.fn();
      const user = userEvent.setup();

      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          onAddItem={onAddItem}
        />
      );

      const addButtons = screen.getAllByText('Add Item');
      await user.click(addButtons[0]);

      expect(onAddItem).toHaveBeenCalledWith('todo');
    });
  });

  describe('Custom Renderers', () => {
    it('uses custom column header renderer', () => {
      const renderColumnHeader = (column: KanbanColumnType<TestItem>) => (
        <div data-testid={`custom-header-${column.id}`}>
          Custom: {column.title}
        </div>
      );

      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          renderColumnHeader={renderColumnHeader}
        />
      );

      expect(screen.getByTestId('custom-header-todo')).toBeInTheDocument();
      expect(screen.getByText('Custom: To Do')).toBeInTheDocument();
    });

    it('uses custom column footer renderer', () => {
      const renderColumnFooter = (column: KanbanColumnType<TestItem>) => (
        <div data-testid={`custom-footer-${column.id}`}>
          Total: {column.items.length}
        </div>
      );

      render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          renderColumnFooter={renderColumnFooter}
        />
      );

      expect(screen.getByTestId('custom-footer-todo')).toBeInTheDocument();
      expect(screen.getByText('Total: 2')).toBeInTheDocument();
    });
  });

  describe('Column Dimensions', () => {
    it('applies custom column width', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          columnWidth={400}
        />
      );

      const columns = container.querySelectorAll('[style*="width: 400px"]');
      expect(columns.length).toBe(3);
    });

    it('applies custom minimum height', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          minColumnHeight={500}
        />
      );

      const wrapper = container.querySelector('[style*="min-height"]');
      expect(wrapper).toHaveStyle({ minHeight: '500px' });
    });
  });

  describe('Drag and Drop', () => {
    it('items are draggable', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      const draggableItems = container.querySelectorAll('[draggable="true"]');
      expect(draggableItems.length).toBe(3); // 3 items total
    });

    it('handles drag start', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      const draggableItem = container.querySelector('[draggable="true"]');
      expect(draggableItem).toBeInTheDocument();

      // Create mock dataTransfer
      const dataTransfer = {
        effectAllowed: '',
        setDragImage: vi.fn(),
      };

      fireEvent.dragStart(draggableItem!, { dataTransfer });

      expect(dataTransfer.effectAllowed).toBe('move');
    });

    it('handles drag over column', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      // Find a column
      const column = screen.getByText('Done').closest('div[style*="width"]');
      expect(column).toBeInTheDocument();

      const dataTransfer = { dropEffect: '' };
      fireEvent.dragOver(column!, { dataTransfer });

      expect(dataTransfer.dropEffect).toBe('move');
    });

    it('calls onMoveItem on drop', async () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      // Start dragging first item
      const draggableItem = container.querySelector('[draggable="true"]');
      const dataTransfer = {
        effectAllowed: '',
        setDragImage: vi.fn(),
      };
      fireEvent.dragStart(draggableItem!, { dataTransfer });

      // Drop on "Done" column
      const doneColumn = screen.getByText('Done').closest('div[style*="width"]');
      fireEvent.drop(doneColumn!, { dataTransfer: { dropEffect: 'move' } });

      await waitFor(() => {
        expect(onMoveItem).toHaveBeenCalled();
      });
    });

    it('does not call onMoveItem when dropped in same column', async () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      // Start dragging first item (in "To Do" column)
      const draggableItem = container.querySelector('[draggable="true"]');
      const dataTransfer = {
        effectAllowed: '',
        setDragImage: vi.fn(),
      };
      fireEvent.dragStart(draggableItem!, { dataTransfer });

      // Drop on same "To Do" column
      const todoColumn = screen.getByText('To Do').closest('div[style*="width"]');
      fireEvent.drop(todoColumn!, { dataTransfer: { dropEffect: 'move' } });

      await waitFor(() => {
        expect(onMoveItem).not.toHaveBeenCalled();
      });
    });

    it('cleans up on drag end', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
        />
      );

      const draggableItem = container.querySelector('[draggable="true"]');
      const dataTransfer = {
        effectAllowed: '',
        setDragImage: vi.fn(),
      };

      fireEvent.dragStart(draggableItem!, { dataTransfer });
      fireEvent.dragEnd(draggableItem!);

      // Should not show dragging state
      expect(draggableItem).not.toHaveClass('opacity-50');
    });
  });

  describe('CSS Classes', () => {
    it('applies custom className', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          className="custom-board"
        />
      );

      expect(container.querySelector('.custom-board')).toBeInTheDocument();
    });

    it('applies columnsClassName', () => {
      const { container } = render(
        <KanbanBoard
          columns={mockColumns}
          onMoveItem={onMoveItem}
          renderItem={renderItem}
          columnsClassName="custom-columns"
        />
      );

      expect(container.querySelector('.custom-columns')).toBeInTheDocument();
    });
  });
});

// =============================================================================
// KanbanColumn Tests
// =============================================================================

describe('KanbanColumn', () => {
  const mockColumn: KanbanColumnType<TestItem> = {
    id: 'test',
    title: 'Test Column',
    items: [{ id: 1, title: 'Test Item' }],
    color: 'blue',
  };

  const defaultProps = {
    column: mockColumn,
    onDragOver: vi.fn(),
    onDragLeave: vi.fn(),
    onDrop: vi.fn(),
    children: <div>Column Content</div>,
  };

  it('renders column title', () => {
    render(<KanbanColumn {...defaultProps} />);
    expect(screen.getByText('Test Column')).toBeInTheDocument();
  });

  it('shows item count', () => {
    render(<KanbanColumn {...defaultProps} />);
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('renders children', () => {
    render(<KanbanColumn {...defaultProps} />);
    expect(screen.getByText('Column Content')).toBeInTheDocument();
  });

  it('applies correct color classes', () => {
    const { container } = render(<KanbanColumn {...defaultProps} />);
    expect(container.firstChild).toHaveClass('border-blue-500');
  });

  it('shows drag over state', () => {
    const { container } = render(
      <KanbanColumn {...defaultProps} isDragOver={true} />
    );
    expect(container.firstChild).toHaveClass('ring-2');
  });

  it('shows add button when configured', async () => {
    const onAddClick = vi.fn();
    const user = userEvent.setup();

    render(
      <KanbanColumn
        {...defaultProps}
        showAddButton={true}
        onAddClick={onAddClick}
      />
    );

    const addButton = screen.getByText('Add Item');
    await user.click(addButton);

    expect(onAddClick).toHaveBeenCalled();
  });

  it('hides add button when showAddButton is false', () => {
    render(<KanbanColumn {...defaultProps} showAddButton={false} />);
    expect(screen.queryByText('Add Item')).not.toBeInTheDocument();
  });

  it('uses custom header renderer', () => {
    render(
      <KanbanColumn
        {...defaultProps}
        renderHeader={() => <div>Custom Header</div>}
      />
    );
    expect(screen.getByText('Custom Header')).toBeInTheDocument();
  });

  it('uses custom footer renderer', () => {
    render(
      <KanbanColumn
        {...defaultProps}
        renderFooter={() => <div>Custom Footer</div>}
      />
    );
    expect(screen.getByText('Custom Footer')).toBeInTheDocument();
  });

  it('shows column metadata', () => {
    const columnWithMetadata = {
      ...mockColumn,
      metadata: { value: 1000, probability: 75 },
    };

    render(<KanbanColumn {...defaultProps} column={columnWithMetadata} />);

    expect(screen.getByText('1,000')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
  });

  it('applies custom width', () => {
    const { container } = render(<KanbanColumn {...defaultProps} width={400} />);
    expect(container.firstChild).toHaveStyle({ width: '400px' });
  });

  it('handles drag events', () => {
    const onDragOver = vi.fn();
    const onDragLeave = vi.fn();
    const onDrop = vi.fn();

    const { container } = render(
      <KanbanColumn
        {...defaultProps}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      />
    );

    const column = container.firstChild!;
    fireEvent.dragOver(column);
    fireEvent.dragLeave(column);
    fireEvent.drop(column);

    expect(onDragOver).toHaveBeenCalled();
    expect(onDragLeave).toHaveBeenCalled();
    expect(onDrop).toHaveBeenCalled();
  });
});

// =============================================================================
// KanbanCard Tests
// =============================================================================

describe('KanbanCard', () => {
  const defaultProps = {
    onDragStart: vi.fn(),
    onDragEnd: vi.fn(),
    children: <div>Card Content</div>,
  };

  it('renders children', () => {
    render(<KanbanCard {...defaultProps} />);
    expect(screen.getByText('Card Content')).toBeInTheDocument();
  });

  it('is draggable', () => {
    const { container } = render(<KanbanCard {...defaultProps} />);
    expect(container.firstChild).toHaveAttribute('draggable', 'true');
  });

  it('shows drag handle by default', () => {
    const { container } = render(<KanbanCard {...defaultProps} />);
    // GripVertical icon should be present
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('hides drag handle when showHandle is false', () => {
    const { container } = render(
      <KanbanCard {...defaultProps} showHandle={false} />
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeInTheDocument();
  });

  it('applies dragging styles', () => {
    const { container } = render(
      <KanbanCard {...defaultProps} isDragging={true} />
    );
    expect(container.firstChild).toHaveClass('opacity-50');
    expect(container.firstChild).toHaveClass('scale-95');
  });

  it('applies moving animation', () => {
    const { container } = render(
      <KanbanCard {...defaultProps} isMoving={true} />
    );
    expect(container.firstChild).toHaveClass('animate-pulse');
  });

  it('calls onDragStart handler', () => {
    const onDragStart = vi.fn();
    const { container } = render(
      <KanbanCard {...defaultProps} onDragStart={onDragStart} />
    );

    fireEvent.dragStart(container.firstChild!);
    expect(onDragStart).toHaveBeenCalled();
  });

  it('calls onDragEnd handler', () => {
    const onDragEnd = vi.fn();
    const { container } = render(
      <KanbanCard {...defaultProps} onDragEnd={onDragEnd} />
    );

    fireEvent.dragEnd(container.firstChild!);
    expect(onDragEnd).toHaveBeenCalled();
  });

  it('applies custom className', () => {
    const { container } = render(
      <KanbanCard {...defaultProps} className="custom-card" />
    );
    expect(container.firstChild).toHaveClass('custom-card');
  });
});

// =============================================================================
// OpportunityCard Tests
// =============================================================================

describe('OpportunityCard', () => {
  const mockOpportunity = {
    id: 1,
    name: 'Big Deal',
    customerName: 'ACME Corp',
    value: 50000,
    probability: 75,
    closeDate: '2024-12-31',
  };

  it('renders opportunity name', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    expect(screen.getByText('Big Deal')).toBeInTheDocument();
  });

  it('renders customer name', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    expect(screen.getByText('ACME Corp')).toBeInTheDocument();
  });

  it('renders formatted value', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    expect(screen.getByText('50,000')).toBeInTheDocument();
  });

  it('uses custom currency formatter', () => {
    render(
      <OpportunityCard
        opportunity={mockOpportunity}
        formatCurrency={(v) => `$${v.toLocaleString()}`}
      />
    );
    expect(screen.getByText('$50,000')).toBeInTheDocument();
  });

  it('renders probability', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('applies correct probability color (high)', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    const probBadge = screen.getByText('75%');
    expect(probBadge).toHaveClass('text-emerald-400');
  });

  it('applies correct probability color (medium)', () => {
    render(
      <OpportunityCard opportunity={{ ...mockOpportunity, probability: 50 }} />
    );
    const probBadge = screen.getByText('50%');
    expect(probBadge).toHaveClass('text-amber-400');
  });

  it('applies correct probability color (low)', () => {
    render(
      <OpportunityCard opportunity={{ ...mockOpportunity, probability: 20 }} />
    );
    const probBadge = screen.getByText('20%');
    expect(probBadge).toHaveClass('text-slate-400');
  });

  it('renders close date', () => {
    render(<OpportunityCard opportunity={mockOpportunity} />);
    expect(screen.getByText('2024-12-31')).toBeInTheDocument();
  });

  it('uses custom date formatter', () => {
    render(
      <OpportunityCard
        opportunity={mockOpportunity}
        formatDate={(d) => `Due: ${d}`}
      />
    );
    expect(screen.getByText('Due: 2024-12-31')).toBeInTheDocument();
  });

  it('handles click when onClick provided', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(<OpportunityCard opportunity={mockOpportunity} onClick={onClick} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(onClick).toHaveBeenCalled();
  });

  it('renders without customer name', () => {
    const { customerName, ...oppWithoutCustomer } = mockOpportunity;
    render(<OpportunityCard opportunity={oppWithoutCustomer} />);
    expect(screen.getByText('Big Deal')).toBeInTheDocument();
    expect(screen.queryByText('ACME Corp')).not.toBeInTheDocument();
  });
});

// =============================================================================
// TaskCard Tests
// =============================================================================

describe('TaskCard', () => {
  const mockTask = {
    id: 1,
    title: 'Implement feature',
    description: 'Add new functionality to the app',
    priority: 'high' as const,
    dueDate: '2024-12-15',
    assignee: { name: 'John Doe' },
    labels: [
      { name: 'Frontend', color: '#3b82f6' },
      { name: 'Priority', color: '#ef4444' },
    ],
  };

  it('renders task title', () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText('Implement feature')).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<TaskCard task={mockTask} />);
    expect(
      screen.getByText('Add new functionality to the app')
    ).toBeInTheDocument();
  });

  it('renders labels', () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText('Frontend')).toBeInTheDocument();
    expect(screen.getByText('Priority')).toBeInTheDocument();
  });

  it('renders priority badge', () => {
    render(<TaskCard task={mockTask} />);
    const priorityBadge = screen.getByText('high');
    expect(priorityBadge).toHaveClass('text-amber-400');
  });

  it('applies correct priority colors', () => {
    const priorities = ['low', 'medium', 'high', 'urgent'] as const;
    const expectedColors = ['text-slate-400', 'text-blue-400', 'text-amber-400', 'text-red-400'];

    priorities.forEach((priority, index) => {
      const { unmount } = render(
        <TaskCard task={{ ...mockTask, priority }} />
      );
      expect(screen.getByText(priority)).toHaveClass(expectedColors[index]);
      unmount();
    });
  });

  it('renders due date', () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText('2024-12-15')).toBeInTheDocument();
  });

  it('uses custom date formatter', () => {
    render(
      <TaskCard task={mockTask} formatDate={(d) => `Due: ${d}`} />
    );
    expect(screen.getByText('Due: 2024-12-15')).toBeInTheDocument();
  });

  it('renders assignee initial when no avatar', () => {
    render(<TaskCard task={mockTask} />);
    expect(screen.getByText('J')).toBeInTheDocument();
  });

  it('handles click when onClick provided', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(<TaskCard task={mockTask} onClick={onClick} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(onClick).toHaveBeenCalled();
  });

  it('renders without optional fields', () => {
    const minimalTask = { id: 1, title: 'Simple Task' };
    render(<TaskCard task={minimalTask} />);
    expect(screen.getByText('Simple Task')).toBeInTheDocument();
  });

  it('renders without labels', () => {
    const { labels, ...taskWithoutLabels } = mockTask;
    render(<TaskCard task={taskWithoutLabels} />);
    expect(screen.getByText('Implement feature')).toBeInTheDocument();
  });
});

// =============================================================================
// Color Utilities Tests
// =============================================================================

describe('getColumnColors', () => {
  it('returns colors for known color key', () => {
    const colors = getColumnColors('blue');
    expect(colors.border).toBe('border-blue-500');
    expect(colors.bg).toBe('bg-blue-500/10');
    expect(colors.header).toBe('bg-blue-900/30');
  });

  it('returns slate colors for unknown color key', () => {
    const colors = getColumnColors('unknown');
    expect(colors).toEqual(KANBAN_COLORS.slate);
  });

  it('returns slate colors for undefined', () => {
    const colors = getColumnColors(undefined);
    expect(colors).toEqual(KANBAN_COLORS.slate);
  });

  it('has colors for all standard options', () => {
    const colorKeys = [
      'slate', 'blue', 'cyan', 'teal', 'emerald', 'green',
      'amber', 'orange', 'red', 'rose', 'purple', 'indigo',
    ];

    colorKeys.forEach((colorKey) => {
      const colors = getColumnColors(colorKey);
      expect(colors.border).toBeTruthy();
      expect(colors.bg).toBeTruthy();
      expect(colors.header).toBeTruthy();
    });
  });
});

// =============================================================================
// KANBAN_COLORS Tests
// =============================================================================

describe('KANBAN_COLORS', () => {
  it('has consistent structure for all colors', () => {
    Object.entries(KANBAN_COLORS).forEach(([colorName, colorConfig]) => {
      expect(colorConfig).toHaveProperty('border');
      expect(colorConfig).toHaveProperty('bg');
      expect(colorConfig).toHaveProperty('header');
      expect(colorConfig.border).toContain(`border-${colorName}-500`);
    });
  });
});
