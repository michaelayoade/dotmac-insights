'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/lists path to new /crm/segments/lists path
export default function ContactsListsRedirect() {
  redirect('/crm/segments/lists');
}
