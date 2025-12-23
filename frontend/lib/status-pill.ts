/**
 * @deprecated Use design-tokens.ts instead for status styling.
 *
 * Migration:
 *   import { getStatusVariant, formatStatusLabel, VARIANT_COLORS } from '@/lib/design-tokens';
 *   import { StatusBadge } from '@/components/Badge';
 *
 * Or use StatusBadge component directly:
 *   <StatusBadge status="pending" />
 */

// Re-export from design-tokens for backwards compatibility
export {
  getStatusVariant,
  formatStatusLabel,
  VARIANT_COLORS as STATUS_PILL_TONES,
  type Variant as StatusTone,
} from './design-tokens';
