'use client';

import { redirect } from 'next/navigation';

// Redirect from old /sales/activities/new path to new /crm/activities/new path
export default function SalesActivityNewRedirect() {
  redirect('/crm/activities/new');
}
