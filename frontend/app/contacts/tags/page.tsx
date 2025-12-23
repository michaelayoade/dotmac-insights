'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/tags path to new /crm/segments/tags path
export default function ContactsTagsRedirect() {
  redirect('/crm/segments/tags');
}
