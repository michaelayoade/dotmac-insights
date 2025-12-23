import type { ElementType } from 'react';
import { Mail, MessageCircle, Phone } from 'lucide-react';

export const INBOX_PERIOD_OPTIONS = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
];

export const INBOX_CHANNEL_CHART_COLORS: Record<string, string> = {
  email: '#3b82f6',
  chat: '#10b981',
  whatsapp: '#22c55e',
  phone: '#8b5cf6',
  sms: '#06b6d4',
  social: '#ec4899',
};

export const INBOX_CHANNEL_COLOR_CLASSES: Record<string, string> = {
  email: 'text-blue-400 bg-blue-500/10',
  chat: 'text-emerald-400 bg-emerald-500/10',
  whatsapp: 'text-green-400 bg-green-500/10',
  phone: 'text-violet-400 bg-violet-500/10',
  sms: 'text-cyan-400 bg-cyan-500/10',
  social: 'text-pink-400 bg-pink-500/10',
};

export const INBOX_CHANNEL_ICON_MAP: Record<string, ElementType> = {
  email: Mail,
  chat: MessageCircle,
  whatsapp: MessageCircle,
  phone: Phone,
  sms: MessageCircle,
  social: MessageCircle,
};

export const formatInboxResponseTime = (hours: number | null | undefined): string => {
  if (hours === null || hours === undefined) return '-';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
};
