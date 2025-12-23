'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/customers path to new /crm/contacts/customers path
export default function ContactsCustomersRedirect() {
  redirect('/crm/contacts/customers');
}
