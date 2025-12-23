'use client';

import { redirect } from 'next/navigation';
import { useParams } from 'next/navigation';

// Redirect from old /sales/opportunities/[id] path to new /crm/pipeline/opportunities/[id] path
export default function SalesOpportunityDetailRedirect() {
  const params = useParams();
  const id = params.id as string;
  redirect(`/crm/pipeline/opportunities/${id}`);
}
