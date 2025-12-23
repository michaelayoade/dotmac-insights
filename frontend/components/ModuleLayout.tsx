/**
 * ModuleLayout - Backwards compatibility re-export
 *
 * The ModuleLayout component has been decomposed into a modular directory structure.
 * This file re-exports everything for backwards compatibility.
 *
 * New code should import from '@/components/ModuleLayout' (the directory)
 * which resolves to '@/components/ModuleLayout/index.ts'.
 *
 * @example
 * // Preferred (imports from directory)
 * import { ModuleLayout } from '@/components/ModuleLayout';
 * import type { NavSection, QuickLink } from '@/components/ModuleLayout';
 *
 * // Also works (this file)
 * import ModuleLayout from '@/components/ModuleLayout';
 */

// Re-export everything from the directory
export * from './ModuleLayout/index';

// Default export for backwards compatibility
export { default } from './ModuleLayout/index';
