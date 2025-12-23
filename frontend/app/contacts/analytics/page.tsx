'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/analytics path to new /crm/analytics path
export default function ContactsAnalyticsRedirect() {
  redirect('/crm/analytics');
}
