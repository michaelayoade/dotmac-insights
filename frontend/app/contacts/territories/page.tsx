'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/territories path to new /crm/segments/territories path
export default function ContactsTerritoriesRedirect() {
  redirect('/crm/segments/territories');
}
