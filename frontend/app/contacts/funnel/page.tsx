'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/funnel path to new /crm/lifecycle/funnel path
export default function ContactsFunnelRedirect() {
  redirect('/crm/lifecycle/funnel');
}
