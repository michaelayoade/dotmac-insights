'use client';

import { redirect } from 'next/navigation';

// Redirect from old /contacts/categories path to new /crm/segments/categories path
export default function ContactsCategoriesRedirect() {
  redirect('/crm/segments/categories');
}
