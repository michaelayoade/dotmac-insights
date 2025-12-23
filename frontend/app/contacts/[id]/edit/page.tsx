'use client';

import { redirect } from 'next/navigation';
import { useParams } from 'next/navigation';

// Redirect from old /contacts/[id]/edit path to new /crm/contacts/[id]/edit path
export default function ContactEditRedirect() {
  const params = useParams();
  const id = params.id as string;
  redirect(`/crm/contacts/${id}/edit`);
}
