'use client';

import Link from 'next/link';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModuleLayoutContext } from './context';
import type { NavSection as NavSectionType } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface NavSectionProps {
  section: NavSectionType;
  /** Callback when navigating (e.g., to close mobile menu) */
  onNavigate?: () => void;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Collapsible navigation section with icon and items
 */
export function NavSection({ section, onNavigate }: NavSectionProps) {
  const { colors, activeSection, activeHref, openSections, toggleSection } = useModuleLayoutContext();

  const Icon = section.icon;
  const isOpen = openSections[section.key];
  const isActiveSection = activeSection === section.key;

  return (
    <div
      className={cn(
        'border rounded-lg transition-colors',
        isActiveSection ? `${colors.activeBorder} ${colors.activeBg}` : 'border-slate-border'
      )}
    >
      <button
        onClick={() => toggleSection(section.key)}
        className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-foreground hover:bg-slate-elevated/50 rounded-lg transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className={cn('w-4 h-4', isActiveSection ? colors.iconText : 'text-slate-muted')} />
          <div className="text-left">
            <span className={cn('block', isActiveSection && colors.activeText)}>{section.label}</span>
            <span className="text-[10px] text-slate-muted">{section.description}</span>
          </div>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-slate-muted" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-muted" />
        )}
      </button>
      {isOpen && (
        <div className="pb-2 px-2">
          {section.items.map((item) => {
            const isActive = activeHref === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  'block px-3 py-2 text-sm rounded-lg transition-colors group',
                  isActive
                    ? `${colors.activeItemBg} ${colors.activeItemText}`
                    : 'text-slate-muted hover:text-foreground hover:bg-slate-elevated/50'
                )}
              >
                <span className="block">{item.name}</span>
                {item.description && (
                  <span
                    className={cn(
                      'text-[10px] block',
                      isActive ? colors.activeDescText : 'text-slate-muted group-hover:text-slate-muted'
                    )}
                  >
                    {item.description}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// NAV SECTIONS LIST
// =============================================================================

interface NavSectionsListProps {
  /** Callback when navigating (e.g., to close mobile menu) */
  onNavigate?: () => void;
}

/**
 * Renders all navigation sections
 */
export function NavSectionsList({ onNavigate }: NavSectionsListProps) {
  const { sections } = useModuleLayoutContext();

  return (
    <div className="space-y-2">
      {sections.map((section) => (
        <NavSection key={section.key} section={section} onNavigate={onNavigate} />
      ))}
    </div>
  );
}
