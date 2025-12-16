'use client';

/**
 * App shell wrapper. All modules now use their own ModuleLayout, so this
 * simply renders children directly. The root page (/) serves as a module
 * chooser and doesn't need a sidebar.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
