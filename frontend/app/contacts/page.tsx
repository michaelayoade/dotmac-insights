'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts path to new /crm path
export default function ContactsRedirect() {
  redirect('/crm');
}
