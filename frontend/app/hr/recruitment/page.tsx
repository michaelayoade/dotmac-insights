'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import { useHrJobOpenings, useHrJobApplicants, useHrJobOffers } from '@/hooks/useApi';
import { cn, formatDate } from '@/lib/utils';
import { Briefcase, FileSignature, UserSearch } from 'lucide-react';

function extractList<T>(response: any) {
  const items = response?.data || [];
  const total = response?.total ?? items.length;
  return { items, total };
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone = 'text-teal-electric',
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  tone?: string;
}) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-slate-muted text-sm">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
      <div className="p-2 rounded-lg bg-slate-elevated">
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
    </div>
  );
}

export default function HrRecruitmentPage() {
  const [openingStatus, setOpeningStatus] = useState('open');
  const [offerStatus, setOfferStatus] = useState('');
  const [openingOffset, setOpeningOffset] = useState(0);
  const [openingLimit, setOpeningLimit] = useState(20);
  const [applicantOffset, setApplicantOffset] = useState(0);
  const [applicantLimit, setApplicantLimit] = useState(20);
  const [offerOffset, setOfferOffset] = useState(0);
  const [offerLimit, setOfferLimit] = useState(20);

  const { data: jobOpenings, isLoading: openingsLoading } = useHrJobOpenings({
    status: openingStatus || undefined,
    limit: openingLimit,
    offset: openingOffset,
  });
  const { data: jobApplicants, isLoading: applicantsLoading } = useHrJobApplicants({
    limit: applicantLimit,
    offset: applicantOffset,
  });
  const { data: jobOffers, isLoading: offersLoading } = useHrJobOffers({
    status: offerStatus || undefined,
    limit: offerLimit,
    offset: offerOffset,
  });

  const openingList = extractList(jobOpenings);
  const applicantList = extractList(jobApplicants);
  const offerList = extractList(jobOffers);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Openings" value={openingList.total} icon={Briefcase} tone="text-teal-electric" />
        <StatCard label="Applicants" value={applicantList.total} icon={UserSearch} tone="text-purple-300" />
        <StatCard label="Offers" value={offerList.total} icon={FileSignature} tone="text-green-300" />
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={openingStatus}
          onChange={(e) => {
            setOpeningStatus(e.target.value);
            setOpeningOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All openings</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </select>
        <select
          value={offerStatus}
          onChange={(e) => {
            setOfferStatus(e.target.value);
            setOfferOffset(0);
          }}
          className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
        >
          <option value="">All offers</option>
          <option value="draft">Draft</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Job Openings</h3>
        </div>
        <DataTable
          columns={[
            { key: 'job_title', header: 'Role', render: (item: any) => <span className="text-white">{item.job_title}</span> },
            { key: 'company', header: 'Company', render: (item: any) => <span className="text-slate-muted text-sm">{item.company || '—'}</span> },
            { key: 'posting_date', header: 'Posted', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.posting_date)}</span> },
            { key: 'expected_date', header: 'Closing', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.expected_date)}</span> },
            { key: 'vacancies', header: 'Vacancies', align: 'right' as const, render: (item: any) => <span className="font-mono text-white">{item.vacancies ?? '—'}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'open' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-slate-border text-slate-muted')}>
                  {item.status || 'open'}
                </span>
              ),
            },
          ]}
          data={(openingList.items || []).map((item: any) => ({ ...item, id: item.id || item.job_title }))}
          keyField="id"
          loading={openingsLoading}
          emptyMessage="No job openings"
        />
        {openingList.total > openingLimit && (
          <Pagination
            total={openingList.total}
            limit={openingLimit}
            offset={openingOffset}
            onPageChange={setOpeningOffset}
            onLimitChange={(val) => {
              setOpeningLimit(val);
              setOpeningOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <UserSearch className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Job Applicants</h3>
        </div>
        <DataTable
          columns={[
            { key: 'applicant_name', header: 'Name', render: (item: any) => <span className="text-white">{item.applicant_name}</span> },
            { key: 'email_id', header: 'Email', render: (item: any) => <span className="text-slate-muted text-sm">{item.email_id}</span> },
            { key: 'job_title', header: 'Job Title', render: (item: any) => <span className="text-slate-muted text-sm">{item.job_title || '—'}</span> },
            { key: 'application_date', header: 'Applied', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.application_date)}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'open' ? 'border-green-400 text-green-300 bg-green-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'open'}
                </span>
              ),
            },
          ]}
          data={(applicantList.items || []).map((item: any) => ({ ...item, id: item.id || item.applicant_id || item.email_id }))}
          keyField="id"
          loading={applicantsLoading}
          emptyMessage="No applicants"
        />
        {applicantList.total > applicantLimit && (
          <Pagination
            total={applicantList.total}
            limit={applicantLimit}
            offset={applicantOffset}
            onPageChange={setApplicantOffset}
            onLimitChange={(val) => {
              setApplicantLimit(val);
              setApplicantOffset(0);
            }}
          />
        )}
      </div>

      <div className="bg-slate-card border border-slate-border rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <FileSignature className="w-4 h-4 text-teal-electric" />
          <h3 className="text-white font-semibold">Job Offers</h3>
        </div>
        <DataTable
          columns={[
            { key: 'job_applicant_name', header: 'Applicant', render: (item: any) => <span className="text-white">{item.job_applicant_name || item.job_applicant}</span> },
            { key: 'job_title', header: 'Role', render: (item: any) => <span className="text-slate-muted text-sm">{item.job_title || '—'}</span> },
            { key: 'offer_date', header: 'Offer Date', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.offer_date)}</span> },
            { key: 'salary_structure', header: 'Salary Structure', render: (item: any) => <span className="text-slate-muted text-sm">{item.salary_structure || '—'}</span> },
            {
              key: 'status',
              header: 'Status',
              render: (item: any) => (
                <span className={cn('px-2 py-1 rounded-full text-xs border capitalize', item.status === 'accepted' ? 'border-green-400 text-green-300 bg-green-500/10' : item.status === 'rejected' ? 'border-red-400 text-red-300 bg-red-500/10' : 'border-amber-400 text-amber-300 bg-amber-500/10')}>
                  {item.status || 'draft'}
                </span>
              ),
            },
          ]}
          data={(offerList.items || []).map((item: any) => ({ ...item, id: item.id || item.job_applicant }))}
          keyField="id"
          loading={offersLoading}
          emptyMessage="No job offers"
        />
        {offerList.total > offerLimit && (
          <Pagination
            total={offerList.total}
            limit={offerLimit}
            offset={offerOffset}
            onPageChange={setOfferOffset}
            onLimitChange={(val) => {
              setOfferLimit(val);
              setOfferOffset(0);
            }}
          />
        )}
      </div>
    </div>
  );
}
