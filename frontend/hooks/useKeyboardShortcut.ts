/**
 * Keyboard shortcut hook for global hotkeys
 */

import { useEffect, useCallback } from 'react';

interface UseKeyboardShortcutOptions {
  /** Require Ctrl key (Windows/Linux) */
  ctrl?: boolean;
  /** Require Meta/Cmd key (Mac) */
  meta?: boolean;
  /** Require Shift key */
  shift?: boolean;
  /** Require Alt key */
  alt?: boolean;
  /** Whether the shortcut is enabled */
  enabled?: boolean;
  /** Prevent default browser behavior */
  preventDefault?: boolean;
}

/**
 * Hook for registering global keyboard shortcuts
 *
 * @example
 * // Cmd+K / Ctrl+K to open search
 * useKeyboardShortcut('k', () => setOpen(true), { meta: true, ctrl: true });
 *
 * // Escape to close
 * useKeyboardShortcut('Escape', () => setOpen(false));
 */
export function useKeyboardShortcut(
  key: string,
  callback: () => void,
  options: UseKeyboardShortcutOptions = {}
) {
  const {
    ctrl = false,
    meta = false,
    shift = false,
    alt = false,
    enabled = true,
    preventDefault = true,
  } = options;

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Check if we're in an input field (unless it's Escape)
      const isInputElement =
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        (event.target instanceof HTMLElement && event.target.isContentEditable);

      // Allow Escape in input fields, but block other shortcuts
      if (isInputElement && key !== 'Escape') {
        // Allow Cmd+K / Ctrl+K even in inputs
        if (!(key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey))) {
          return;
        }
      }

      // Check if the key matches
      const keyMatches =
        event.key.toLowerCase() === key.toLowerCase() ||
        event.code.toLowerCase() === `key${key.toLowerCase()}`;

      if (!keyMatches) return;

      // Check modifier keys
      // For meta/ctrl, we accept either one being pressed
      const modifierMatches =
        (meta || ctrl ? event.metaKey || event.ctrlKey : !event.metaKey && !event.ctrlKey) &&
        (shift ? event.shiftKey : !event.shiftKey) &&
        (alt ? event.altKey : !event.altKey);

      if (!modifierMatches) return;

      if (preventDefault) {
        event.preventDefault();
        event.stopPropagation();
      }

      callback();
    },
    [key, callback, ctrl, meta, shift, alt, enabled, preventDefault]
  );

  useEffect(() => {
    if (!enabled) return;

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown, enabled]);
}

/**
 * Hook for registering multiple keyboard shortcuts
 *
 * @example
 * useKeyboardShortcuts([
 *   { key: 'k', callback: () => openSearch(), meta: true, ctrl: true },
 *   { key: 'Escape', callback: () => closeSearch() },
 * ]);
 */
export function useKeyboardShortcuts(
  shortcuts: Array<{ key: string; callback: () => void } & UseKeyboardShortcutOptions>
) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const {
          key,
          callback,
          ctrl = false,
          meta = false,
          shift = false,
          alt = false,
          enabled = true,
          preventDefault = true,
        } = shortcut;

        if (!enabled) continue;

        const isInputElement =
          event.target instanceof HTMLInputElement ||
          event.target instanceof HTMLTextAreaElement ||
          (event.target instanceof HTMLElement && event.target.isContentEditable);

        if (isInputElement && key !== 'Escape') {
          if (!(key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey))) {
            continue;
          }
        }

        const keyMatches =
          event.key.toLowerCase() === key.toLowerCase() ||
          event.code.toLowerCase() === `key${key.toLowerCase()}`;

        if (!keyMatches) continue;

        const modifierMatches =
          (meta || ctrl ? event.metaKey || event.ctrlKey : !event.metaKey && !event.ctrlKey) &&
          (shift ? event.shiftKey : !event.shiftKey) &&
          (alt ? event.altKey : !event.altKey);

        if (!modifierMatches) continue;

        if (preventDefault) {
          event.preventDefault();
          event.stopPropagation();
        }

        callback();
        break; // Only trigger one shortcut
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}
