'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/all path to new /crm/contacts/all path
export default function ContactsAllRedirect() {
  redirect('/crm/contacts/all');
}
