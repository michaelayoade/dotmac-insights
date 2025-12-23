'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/organizations path to new /crm/contacts/organizations path
export default function ContactsOrganizationsRedirect() {
  redirect('/crm/contacts/organizations');
}
