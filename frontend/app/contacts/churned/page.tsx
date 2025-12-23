'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/churned path to new /crm/contacts/churned path
export default function ContactsChurnedRedirect() {
  redirect('/crm/contacts/churned');
}
