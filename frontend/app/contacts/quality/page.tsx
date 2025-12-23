'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/quality path to new /crm/tools/quality path
export default function ContactsQualityRedirect() {
  redirect('/crm/tools/quality');
}
