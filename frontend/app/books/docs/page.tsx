'use client';

import Link from 'next/link';
import { BookOpen, Download, ExternalLink, LifeBuoy, FileText } from 'lucide-react';

const resources = [
  {
    title: 'Books overview',
    description: 'Understand how AR, AP, banking, and reporting fit together.',
    href: '/books',
    icon: BookOpen,
  },
  {
    title: 'Exports & docs',
    description: 'Download ledgers, statements, VAT schedules, and audit exports.',
    href: '/books',
    icon: Download,
  },
  {
    title: 'Chart of accounts',
    description: 'See your configured accounts and structure.',
    href: '/books/chart-of-accounts',
    icon: FileText,
  },
];

export default function BooksDocsPage() {
  return (
    <div className="space-y-10">
      <div className="rounded-xl border border-slate-border bg-slate-card p-6 shadow-sm">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-gradient-to-br from-teal-electric to-teal-glow p-2 text-slate-deep">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-muted">Books</p>
              <h1 className="text-xl font-semibold text-white">Docs & Exports</h1>
            </div>
          </div>
          <p className="text-sm text-slate-muted">
            Quick references and helpful links to get around Books. Use the cards below to jump into key areas or scroll
            for help.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {resources.map((item) => (
          <Link
            key={item.title}
            href={item.href}
            className="group rounded-xl border border-slate-border bg-slate-900/40 p-4 transition hover:-translate-y-0.5 hover:border-teal-electric hover:bg-slate-900/70"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-slate-800 p-2 text-teal-200 group-hover:bg-slate-700">
                <item.icon className="h-4 w-4" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-white">{item.title}</p>
                <p className="text-sm text-slate-muted">{item.description}</p>
              </div>
              <ExternalLink className="h-4 w-4 text-slate-muted" />
            </div>
          </Link>
        ))}
      </div>

      <div
        id="help"
        className="rounded-xl border border-slate-border bg-slate-card p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-amber-500/10 p-2 text-amber-300">
            <LifeBuoy className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-muted">Help</p>
            <h2 className="text-lg font-semibold text-white">How to use Books</h2>
          </div>
        </div>
        <div className="mt-4 space-y-3 text-sm text-slate-muted">
          <p>
            Start with the Dashboard to see KPIs and shortcuts. Capture sales in Accounts Receivable, purchases in
            Accounts Payable, reconcile activity in Banking, then publish reports from Balance Sheet, Income Statement,
            or Trial Balance.
          </p>
          <p>
            Need a walkthrough or facing an issue? Reach out to your admin or support channel with the page URL and a
            short note of what you were doing.
          </p>
        </div>
      </div>
    </div>
  );
}
