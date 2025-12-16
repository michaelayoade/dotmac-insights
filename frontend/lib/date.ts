/**
 * Lightweight date utilities to avoid external dependencies.
 */

function toDate(input: Date | string | number | null | undefined): Date | null {
  if (!input) return null;
  const d = input instanceof Date ? input : new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(input: Date | string | number | null | undefined, pattern: string): string {
  const date = toDate(input);
  if (!date) return '';

  switch (pattern) {
    case 'yyyy-MM-dd':
      return date.toISOString().slice(0, 10);
    case 'MMM d, yyyy':
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    case 'MMM d':
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    case 'h:mm a': {
      const hours = date.getHours();
      const minutes = date.getMinutes();
      const suffix = hours >= 12 ? 'PM' : 'AM';
      const hour12 = hours % 12 === 0 ? 12 : hours % 12;
      const paddedMin = minutes.toString().padStart(2, '0');
      return `${hour12}:${paddedMin} ${suffix}`;
    }
    default:
      return date.toLocaleDateString();
  }
}

export function formatDistanceToNow(input: Date | string | number | null | undefined): string {
  const date = toDate(input);
  if (!date) return '';
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 45) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

export function isToday(input: Date | string | number | null | undefined): boolean {
  const date = toDate(input);
  if (!date) return false;
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

export function isTomorrow(input: Date | string | number | null | undefined): boolean {
  const date = toDate(input);
  if (!date) return false;
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return (
    date.getFullYear() === tomorrow.getFullYear() &&
    date.getMonth() === tomorrow.getMonth() &&
    date.getDate() === tomorrow.getDate()
  );
}

export function isPast(input: Date | string | number | null | undefined): boolean {
  const date = toDate(input);
  if (!date) return false;
  const now = new Date();
  return date.getTime() < now.setHours(0, 0, 0, 0);
}
