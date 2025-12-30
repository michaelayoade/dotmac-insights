/**
 * usePagination Hook Tests
 *
 * Tests for pagination state management including:
 * - Initial state
 * - Page navigation
 * - Page size changes
 * - API parameter generation
 * - Utility functions
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePagination } from './usePagination';

describe('usePagination', () => {
  describe('Initial State', () => {
    it('initializes with default values', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.page).toBe(1);
      expect(result.current.pageSize).toBe(20);
      expect(result.current.offset).toBe(0);
    });

    it('accepts custom initial page size', () => {
      const { result } = renderHook(() =>
        usePagination({ initialPageSize: 50 })
      );

      expect(result.current.pageSize).toBe(50);
      expect(result.current.pageSizeOptions).toEqual([20, 50, 100]);
    });

    it('accepts custom page size options', () => {
      const { result } = renderHook(() =>
        usePagination({ pageSizeOptions: [10, 25, 50] })
      );

      expect(result.current.pageSizeOptions).toEqual([10, 25, 50]);
    });
  });

  describe('Offset Calculation', () => {
    it('calculates offset correctly for page 1', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.offset).toBe(0);
    });

    it('calculates offset correctly for page 2', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(2);
      });

      expect(result.current.offset).toBe(20);
    });

    it('calculates offset correctly with custom page size', () => {
      const { result } = renderHook(() =>
        usePagination({ initialPageSize: 50 })
      );

      act(() => {
        result.current.setPage(3);
      });

      expect(result.current.offset).toBe(100);
    });
  });

  describe('Page Navigation', () => {
    it('setPage changes current page', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(5);
      });

      expect(result.current.page).toBe(5);
    });

    it('setPage prevents negative pages', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(-1);
      });

      expect(result.current.page).toBe(1);
    });

    it('nextPage increments page', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.nextPage();
      });

      expect(result.current.page).toBe(2);
    });

    it('prevPage decrements page', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(3);
      });

      act(() => {
        result.current.prevPage();
      });

      expect(result.current.page).toBe(2);
    });

    it('prevPage stops at page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.prevPage();
      });

      expect(result.current.page).toBe(1);
    });

    it('goToFirst resets to page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(10);
      });

      act(() => {
        result.current.goToFirst();
      });

      expect(result.current.page).toBe(1);
    });

    it('goToLast goes to calculated last page', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.goToLast(95); // 95 items with 20 per page = 5 pages
      });

      expect(result.current.page).toBe(5);
    });

    it('reset returns to page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(5);
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.page).toBe(1);
    });
  });

  describe('Page Size Changes', () => {
    it('setPageSize updates page size', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPageSize(50);
      });

      expect(result.current.pageSize).toBe(50);
    });

    it('setPageSize resets to page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(5);
      });

      act(() => {
        result.current.setPageSize(50);
      });

      expect(result.current.page).toBe(1);
    });
  });

  describe('onPageChange Handler', () => {
    it('converts offset to page correctly', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.onPageChange(40);
      });

      expect(result.current.page).toBe(3);
      expect(result.current.offset).toBe(40);
    });

    it('handles offset 0', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(5);
      });

      act(() => {
        result.current.onPageChange(0);
      });

      expect(result.current.page).toBe(1);
    });
  });

  describe('onLimitChange Handler', () => {
    it('updates page size and resets to page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(3);
      });

      act(() => {
        result.current.onLimitChange(50);
      });

      expect(result.current.pageSize).toBe(50);
      expect(result.current.page).toBe(1);
    });
  });

  describe('API Params', () => {
    it('getApiParams returns limit and offset', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.getApiParams()).toEqual({
        limit: 20,
        offset: 0,
      });
    });

    it('getApiParams reflects current state', () => {
      const { result } = renderHook(() =>
        usePagination({ initialPageSize: 50 })
      );

      act(() => {
        result.current.setPage(3);
      });

      expect(result.current.getApiParams()).toEqual({
        limit: 50,
        offset: 100,
      });
    });
  });

  describe('Total Pages Calculation', () => {
    it('getTotalPages calculates correctly', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.getTotalPages(100)).toBe(5);
      expect(result.current.getTotalPages(101)).toBe(6);
      expect(result.current.getTotalPages(95)).toBe(5);
    });

    it('getTotalPages returns at least 1', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.getTotalPages(0)).toBe(1);
    });
  });

  describe('Navigation Helpers', () => {
    it('hasNextPage returns true when more pages exist', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.hasNextPage(100)).toBe(true);
    });

    it('hasNextPage returns false on last page', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(5);
      });

      expect(result.current.hasNextPage(100)).toBe(false);
    });

    it('hasPrevPage returns false on page 1', () => {
      const { result } = renderHook(() => usePagination());

      expect(result.current.hasPrevPage()).toBe(false);
    });

    it('hasPrevPage returns true after page 1', () => {
      const { result } = renderHook(() => usePagination());

      act(() => {
        result.current.setPage(2);
      });

      expect(result.current.hasPrevPage()).toBe(true);
    });
  });
});
