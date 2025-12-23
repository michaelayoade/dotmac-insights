'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/new path to new /crm/contacts/new path
export default function ContactsNewRedirect() {
  redirect('/crm/contacts/new');
}
