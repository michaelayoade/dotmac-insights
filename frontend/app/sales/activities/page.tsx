'use client';

import { redirect } from 'next/navigation';

// Redirect from old /sales/activities path to new /crm/activities path
export default function SalesActivitiesRedirect() {
  redirect('/crm/activities');
}
