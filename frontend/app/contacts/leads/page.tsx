'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/leads path to new /crm/contacts/leads path
export default function ContactsLeadsRedirect() {
  redirect('/crm/contacts/leads');
}
