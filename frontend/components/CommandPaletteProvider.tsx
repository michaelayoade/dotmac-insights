'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { CommandPalette } from './CommandPalette';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';

// =============================================================================
// CONTEXT
// =============================================================================

interface CommandPaletteContextValue {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(null);

// =============================================================================
// PROVIDER
// =============================================================================

interface CommandPaletteProviderProps {
  children: ReactNode;
}

/**
 * Provider for the global command palette
 *
 * @example
 * // In app/layout.tsx
 * <CommandPaletteProvider>
 *   {children}
 * </CommandPaletteProvider>
 *
 * // In any component
 * const { open } = useCommandPalette();
 * <button onClick={open}>Search</button>
 */
export function CommandPaletteProvider({ children }: CommandPaletteProviderProps) {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  // Cmd+K / Ctrl+K to open
  useKeyboardShortcut('k', toggle, { meta: true, ctrl: true });

  return (
    <CommandPaletteContext.Provider value={{ isOpen, open, close, toggle }}>
      {children}
      <CommandPalette isOpen={isOpen} onClose={close} />
    </CommandPaletteContext.Provider>
  );
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Hook to access command palette controls
 *
 * @example
 * const { open, close, toggle, isOpen } = useCommandPalette();
 */
export function useCommandPalette(): CommandPaletteContextValue {
  const context = useContext(CommandPaletteContext);

  if (!context) {
    throw new Error('useCommandPalette must be used within a CommandPaletteProvider');
  }

  return context;
}

export default CommandPaletteProvider;
