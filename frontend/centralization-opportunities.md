# Frontend centralization opportunities (heuristic)

## Repeated array literal (3 occurrences)
- frontend/app/inbox/analytics/page.tsx:periodOptions
- frontend/app/inbox/analytics/channels/page.tsx:dayOptions
- frontend/app/inbox/analytics/agents/page.tsx:dayOptions

Sample:

[ { value: '7', label: 'Last 7 days' }, { value: '30', label: 'Last 30 days' }, { value: '90', label: 'Last 90 days' }, ]

## Repeated array literal (2 occurrences)
- frontend/app/books/trial-balance/page.tsx:columns
- frontend/app/accounting/trial-balance/page.tsx:columns

Sample:

[ { key: 'account_number', header: 'Account #', sortable: true, render: (item: any) => ( <span className="font-mono text-teal-electric">{item.account_number}</span> ), }, { key: 'account_name', header: 'Account Name', sortable: true, render...

## Repeated array literal (2 occurrences)
- frontend/app/books/suppliers/page.tsx:columns
- frontend/app/accounting/suppliers/page.tsx:columns

Sample:

[ { key: 'name', header: 'Supplier Name', sortable: true, render: (item: any) => ( <div className="flex items-center gap-2"> <Building className="w-4 h-4 text-teal-electric" /> <span className="text-foreground font-medium">{item.name || ite...

## Repeated array literal (2 occurrences)
- frontend/app/books/chart-of-accounts/page.tsx:columns
- frontend/app/accounting/chart-of-accounts/page.tsx:columns

Sample:

[ { key: 'account_number', header: 'Account #', sortable: true, render: (item: any) => ( <div className="flex items-center gap-2"> <BookOpen className="w-4 h-4 text-teal-electric" /> <span className="font-mono text-teal-electric">{item.acco...

## Repeated array literal (2 occurrences)
- frontend/app/books/general-ledger/page.tsx:columns
- frontend/app/accounting/general-ledger/page.tsx:columns

Sample:

[ { key: 'date', header: 'Date', sortable: true, render: (item: AccountingGeneralLedgerEntry) => ( <span className="text-slate-muted">{formatDate(item.posting_date)}</span> ), }, { key: 'account', header: 'Account', render: (item: Accountin...
