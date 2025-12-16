'use client';

import { useEffect, useState } from 'react';

/**
 * Persist lightweight UI state (filters, tabs) in localStorage.
 * Merges parsed state over the provided default to allow additive fields.
 */
export function usePersistentState<T extends Record<string, any>>(key: string, defaultValue: T) {
  const [state, setState] = useState<T>(() => {
    if (typeof window === 'undefined') return defaultValue;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return defaultValue;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return { ...defaultValue, ...parsed };
      }
    } catch (error) {
      console.warn('Failed to read persistent state', error);
    }
    return defaultValue;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch (error) {
      console.warn('Failed to persist state', error);
    }
  }, [key, state]);

  return [state, setState] as const;
}
