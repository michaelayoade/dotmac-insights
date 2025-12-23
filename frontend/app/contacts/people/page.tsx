'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/people path to new /crm/contacts/people path
export default function ContactsPeopleRedirect() {
  redirect('/crm/contacts/people');
}
