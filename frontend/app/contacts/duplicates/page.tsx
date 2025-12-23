'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/duplicates path to new /crm/tools/duplicates path
export default function ContactsDuplicatesRedirect() {
  redirect('/crm/tools/duplicates');
}
