/**
 * useDebounce Hook Tests
 *
 * Tests for debouncing hooks including:
 * - useDebounce value debouncing
 * - useDebouncedCallback function debouncing
 * - useDebouncedState combined state management
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebounce, useDebouncedCallback, useDebouncedState } from './useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Value Debouncing', () => {
    it('returns initial value immediately', () => {
      const { result } = renderHook(() => useDebounce('initial', 500));

      expect(result.current).toBe('initial');
    });

    it('does not update value before delay', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 500),
        { initialProps: { value: 'initial' } }
      );

      rerender({ value: 'updated' });

      // Before delay, should still be initial
      expect(result.current).toBe('initial');
    });

    it('updates value after delay', async () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 500),
        { initialProps: { value: 'initial' } }
      );

      rerender({ value: 'updated' });

      act(() => {
        vi.advanceTimersByTime(500);
      });

      expect(result.current).toBe('updated');
    });

    it('resets timer on rapid changes', async () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 500),
        { initialProps: { value: 'initial' } }
      );

      rerender({ value: 'first' });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      rerender({ value: 'second' });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Still initial because timer was reset
      expect(result.current).toBe('initial');

      act(() => {
        vi.advanceTimersByTime(200);
      });

      // Now should be 'second' (500ms since 'second')
      expect(result.current).toBe('second');
    });

    it('handles number values', async () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 300),
        { initialProps: { value: 0 } }
      );

      rerender({ value: 42 });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current).toBe(42);
    });

    it('handles object values', async () => {
      const initial = { count: 0 };
      const updated = { count: 1 };

      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 300),
        { initialProps: { value: initial } }
      );

      rerender({ value: updated });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current).toEqual(updated);
    });
  });
});

describe('useDebouncedCallback', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('delays callback execution', () => {
    const callback = vi.fn();

    const { result } = renderHook(() => useDebouncedCallback(callback, 500));

    result.current('arg1');

    expect(callback).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(callback).toHaveBeenCalledWith('arg1');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('cancels previous call on rapid invocations', () => {
    const callback = vi.fn();

    const { result } = renderHook(() => useDebouncedCallback(callback, 500));

    result.current('first');

    act(() => {
      vi.advanceTimersByTime(300);
    });

    result.current('second');

    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Still not called
    expect(callback).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Called with second argument only
    expect(callback).toHaveBeenCalledWith('second');
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('preserves latest callback', () => {
    const callback1 = vi.fn();
    const callback2 = vi.fn();

    const { result, rerender } = renderHook(
      ({ cb }) => useDebouncedCallback(cb, 500),
      { initialProps: { cb: callback1 } }
    );

    result.current();

    // Update callback before timer fires
    rerender({ cb: callback2 });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Should call the updated callback
    expect(callback1).not.toHaveBeenCalled();
    expect(callback2).toHaveBeenCalled();
  });

  it('cleans up on unmount', () => {
    const callback = vi.fn();

    const { result, unmount } = renderHook(() =>
      useDebouncedCallback(callback, 500)
    );

    result.current();

    unmount();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Should not call after unmount
    expect(callback).not.toHaveBeenCalled();
  });

  it('passes multiple arguments', () => {
    const callback = vi.fn();

    const { result } = renderHook(() => useDebouncedCallback(callback, 300));

    result.current('arg1', 'arg2', 'arg3');

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(callback).toHaveBeenCalledWith('arg1', 'arg2', 'arg3');
  });
});

describe('useDebouncedState', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('provides immediate value updates', () => {
    const { result } = renderHook(() => useDebouncedState('initial', 500));

    expect(result.current.value).toBe('initial');
    expect(result.current.debouncedValue).toBe('initial');

    act(() => {
      result.current.setValue('updated');
    });

    // Immediate value updates right away
    expect(result.current.value).toBe('updated');
    // Debounced value is still old
    expect(result.current.debouncedValue).toBe('initial');
  });

  it('updates debounced value after delay', () => {
    const { result } = renderHook(() => useDebouncedState('initial', 500));

    act(() => {
      result.current.setValue('updated');
    });

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current.value).toBe('updated');
    expect(result.current.debouncedValue).toBe('updated');
  });

  it('works with empty string initial value', () => {
    const { result } = renderHook(() => useDebouncedState('', 300));

    expect(result.current.value).toBe('');
    expect(result.current.debouncedValue).toBe('');
  });
});
