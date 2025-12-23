'use client';

import { redirect } from 'next/navigation';
import { useParams } from 'next/navigation';

// Redirect from old /contacts/[id] path to new /crm/contacts/[id] path
export default function ContactDetailRedirect() {
  const params = useParams();
  const id = params.id as string;
  redirect(`/crm/contacts/${id}`);
}
