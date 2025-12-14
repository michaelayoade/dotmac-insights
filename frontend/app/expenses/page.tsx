import Link from 'next/link';

const links = [
  { href: '/expenses/claims', title: 'Expense Claims', desc: 'Create, submit, and monitor claims' },
  { href: '/expenses/claims/new', title: 'New Claim', desc: 'Capture a new expense claim' },
  { href: '/expenses/advances', title: 'Cash Advances', desc: 'Request and settle advances' },
  { href: '/expenses/advances/new', title: 'New Cash Advance', desc: 'Request pre-funding' },
];

export default function ExpensesDashboard() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {links.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-base font-medium text-gray-900">{item.title}</p>
              <p className="text-sm text-gray-500">{item.desc}</p>
            </div>
            <span className="text-sm text-blue-600">Open →</span>
          </div>
        </Link>
      ))}
    </div>
  );
}
