'use client';

import { redirect } from 'next/navigation';

// Redirect from old /sales/pipeline path to new /crm/pipeline path
export default function SalesPipelineRedirect() {
  redirect('/crm/pipeline');
}
