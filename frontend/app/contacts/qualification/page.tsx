'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/qualification path to new /crm/lifecycle/qualification path
export default function ContactsQualificationRedirect() {
  redirect('/crm/lifecycle/qualification');
}
