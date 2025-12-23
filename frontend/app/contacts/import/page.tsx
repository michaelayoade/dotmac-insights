'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/import path to new /crm/tools/import path
export default function ContactsImportRedirect() {
  redirect('/crm/tools/import');
}
