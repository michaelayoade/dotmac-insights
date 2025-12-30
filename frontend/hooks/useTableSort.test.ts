/**
 * useTableSort Hook Tests
 *
 * Tests for table sorting functionality including:
 * - Initial sort state
 * - Sort toggling
 * - Sort direction changes
 * - Sorting different data types
 * - Edge cases
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTableSort } from './useTableSort';

interface TestItem {
  id: number;
  name: string;
  count: number;
  date: string;
  status: string | null;
}

const mockItems: TestItem[] = [
  { id: 1, name: 'Alice', count: 10, date: '2024-01-15', status: 'active' },
  { id: 2, name: 'bob', count: 5, date: '2024-03-20', status: 'inactive' },
  { id: 3, name: 'Charlie', count: 20, date: '2024-02-10', status: null },
  { id: 4, name: 'david', count: 15, date: '2024-01-01', status: 'pending' },
  { id: 5, name: 'Eve', count: 8, date: '2024-04-05', status: 'active' },
];

type SortField = 'name' | 'count' | 'date' | 'status';

describe('useTableSort', () => {
  describe('Initial State', () => {
    it('initializes with default field and order', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      expect(result.current.sortField).toBe('count');
      expect(result.current.sortOrder).toBe('desc'); // default order
    });

    it('accepts custom default order', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, {
          defaultField: 'name',
          defaultOrder: 'asc',
        })
      );

      expect(result.current.sortField).toBe('name');
      expect(result.current.sortOrder).toBe('asc');
    });
  });

  describe('Sorting Numbers', () => {
    it('sorts numbers in descending order', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      const counts = result.current.sortedItems.map((item) => item.count);
      expect(counts).toEqual([20, 15, 10, 8, 5]);
    });

    it('sorts numbers in ascending order', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, {
          defaultField: 'count',
          defaultOrder: 'asc',
        })
      );

      const counts = result.current.sortedItems.map((item) => item.count);
      expect(counts).toEqual([5, 8, 10, 15, 20]);
    });
  });

  describe('Sorting Strings', () => {
    it('sorts strings case-insensitively descending', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'name' })
      );

      const names = result.current.sortedItems.map((item) => item.name);
      // Descending: Eve, david, Charlie, bob, Alice
      expect(names).toEqual(['Eve', 'david', 'Charlie', 'bob', 'Alice']);
    });

    it('sorts strings case-insensitively ascending', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, {
          defaultField: 'name',
          defaultOrder: 'asc',
        })
      );

      const names = result.current.sortedItems.map((item) => item.name);
      // Ascending: Alice, bob, Charlie, david, Eve
      expect(names).toEqual(['Alice', 'bob', 'Charlie', 'david', 'Eve']);
    });
  });

  describe('Sorting Dates', () => {
    it('sorts date strings descending', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'date' })
      );

      const dates = result.current.sortedItems.map((item) => item.date);
      expect(dates).toEqual([
        '2024-04-05',
        '2024-03-20',
        '2024-02-10',
        '2024-01-15',
        '2024-01-01',
      ]);
    });
  });

  describe('Toggle Sort', () => {
    it('toggles sort order when same field clicked', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      expect(result.current.sortOrder).toBe('desc');

      act(() => {
        result.current.toggleSort('count');
      });

      expect(result.current.sortOrder).toBe('asc');

      act(() => {
        result.current.toggleSort('count');
      });

      expect(result.current.sortOrder).toBe('desc');
    });

    it('changes to desc when different field clicked', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, {
          defaultField: 'count',
          defaultOrder: 'asc',
        })
      );

      expect(result.current.sortField).toBe('count');
      expect(result.current.sortOrder).toBe('asc');

      act(() => {
        result.current.toggleSort('name');
      });

      expect(result.current.sortField).toBe('name');
      expect(result.current.sortOrder).toBe('desc'); // resets to desc
    });
  });

  describe('isActive Helper', () => {
    it('returns true for current sort field', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      expect(result.current.isActive('count')).toBe(true);
      expect(result.current.isActive('name')).toBe(false);
    });

    it('updates when field changes', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      act(() => {
        result.current.toggleSort('name');
      });

      expect(result.current.isActive('count')).toBe(false);
      expect(result.current.isActive('name')).toBe(true);
    });
  });

  describe('Null/Undefined Handling', () => {
    it('handles null values in sort', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'status' })
      );

      // Null values should be treated as empty strings
      const sortedItems = result.current.sortedItems;
      // Item with null status should be sorted consistently
      expect(sortedItems.find((item) => item.status === null)).toBeDefined();
    });
  });

  describe('Empty Items', () => {
    it('handles empty array', () => {
      const { result } = renderHook(() =>
        useTableSort<SortField, TestItem>([], { defaultField: 'count' })
      );

      expect(result.current.sortedItems).toEqual([]);
    });
  });

  describe('Items Update', () => {
    it('re-sorts when items change', () => {
      const { result, rerender } = renderHook(
        ({ items }) =>
          useTableSort<SortField, TestItem>(items, { defaultField: 'count' }),
        { initialProps: { items: mockItems } }
      );

      const initialCounts = result.current.sortedItems.map((item) => item.count);
      expect(initialCounts).toEqual([20, 15, 10, 8, 5]);

      // Add a new item with higher count
      const newItems = [
        ...mockItems,
        { id: 6, name: 'Frank', count: 25, date: '2024-05-01', status: 'active' },
      ];

      rerender({ items: newItems });

      const newCounts = result.current.sortedItems.map((item) => item.count);
      expect(newCounts).toEqual([25, 20, 15, 10, 8, 5]);
    });
  });

  describe('Stable Reference', () => {
    it('returns stable sorted array for same inputs', () => {
      const { result, rerender } = renderHook(() =>
        useTableSort<SortField, TestItem>(mockItems, { defaultField: 'count' })
      );

      const firstResult = result.current.sortedItems;

      rerender();

      // Should be same reference if items haven't changed
      expect(result.current.sortedItems).toBe(firstResult);
    });
  });
});
