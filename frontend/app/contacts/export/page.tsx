'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/export path to new /crm/tools/export path
export default function ContactsExportRedirect() {
  redirect('/crm/tools/export');
}
