'use client';

import { useState } from 'react';
import { DataTable, Pagination } from '@/components/DataTable';
import {
  useHrJobOpenings,
  useHrJobApplicants,
  useHrJobOffers,
  useHrJobApplicantMutations,
  useHrInterviewMutations,
  useHrJobOfferMutations,
  useHrInterviews,
  useHrJobOpeningMutations,
} from '@/hooks/useApi';
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
  const [scheduleForm, setScheduleForm] = useState({ applicantId: '', interview_date: '', interviewer: '', location: '', notes: '' });
  const [makeOfferForm, setMakeOfferForm] = useState({ applicantId: '', offerId: '' });
  const [interviewForm, setInterviewForm] = useState({ applicantId: '', scheduled_at: '', interviewer: '', location: '', mode: 'in-person' });
  const [completeInterviewForm, setCompleteInterviewForm] = useState({ interviewId: '', feedback: '', rating: '', result: '' });
  const [interviewActionId, setInterviewActionId] = useState('');
  const [interviewAction, setInterviewAction] = useState<'cancel' | 'no-show'>('cancel');
  const [offerAction, setOfferAction] = useState<'send' | 'accept' | 'reject' | 'void'>('send');
  const [offerActionId, setOfferActionId] = useState('');
  const [offerVoidReason, setOfferVoidReason] = useState('');
  const [bulkOfferIds, setBulkOfferIds] = useState('');
  const [bulkOfferDelivery, setBulkOfferDelivery] = useState('email');
  const [actionError, setActionError] = useState<string | null>(null);
  const [newOpening, setNewOpening] = useState({
    job_title: '',
    company: '',
    status: 'open',
    posting_date: '',
    expected_date: '',
    vacancies: '',
  });

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
  const { data: interviews, isLoading: interviewsLoading } = useHrInterviews({ limit: 20, offset: 0 });
  const applicantMutations = useHrJobApplicantMutations();
  const interviewMutations = useHrInterviewMutations();
  const offerMutations = useHrJobOfferMutations();
  const jobOpeningMutations = useHrJobOpeningMutations();

  const openingList = extractList(jobOpenings);
  const applicantList = extractList(jobApplicants);
  const offerList = extractList(jobOffers);
  const interviewList = extractList(interviews);

  const handleScheduleInterview = async () => {
    setActionError(null);
    if (!scheduleForm.applicantId || !scheduleForm.interview_date || !scheduleForm.interviewer) {
      setActionError('Applicant, interview date, and interviewer are required.');
      return;
    }
    try {
      await applicantMutations.scheduleInterview(scheduleForm.applicantId, {
        interview_date: scheduleForm.interview_date,
        interviewer: scheduleForm.interviewer,
        location: scheduleForm.location || undefined,
        notes: scheduleForm.notes || undefined,
      });
      setScheduleForm({ applicantId: '', interview_date: '', interviewer: '', location: '', notes: '' });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to schedule interview');
    }
  };

  const handleMakeOffer = async () => {
    setActionError(null);
    if (!makeOfferForm.applicantId || !makeOfferForm.offerId) {
      setActionError('Applicant and offer are required.');
      return;
    }
    try {
      await applicantMutations.makeOffer(makeOfferForm.applicantId, { offer_id: makeOfferForm.offerId });
      setMakeOfferForm({ applicantId: '', offerId: '' });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to attach offer');
    }
  };

  const handleCreateInterview = async () => {
    setActionError(null);
    if (!interviewForm.applicantId || !interviewForm.scheduled_at || !interviewForm.interviewer) {
      setActionError('Applicant, time, and interviewer are required.');
      return;
    }
    try {
      await interviewMutations.create({
        job_applicant_id: Number(interviewForm.applicantId),
        scheduled_at: interviewForm.scheduled_at,
        interviewer: interviewForm.interviewer,
        location: interviewForm.location || undefined,
        mode: interviewForm.mode || undefined,
        status: 'scheduled',
      });
      setInterviewForm({ applicantId: '', scheduled_at: '', interviewer: '', location: '', mode: 'in-person' });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to create interview');
    }
  };

  const handleCompleteInterview = async () => {
    setActionError(null);
    if (!completeInterviewForm.interviewId) {
      setActionError('Interview ID is required.');
      return;
    }
    try {
      await interviewMutations.complete(completeInterviewForm.interviewId, {
        feedback: completeInterviewForm.feedback || undefined,
        rating: completeInterviewForm.rating ? Number(completeInterviewForm.rating) : undefined,
        result: completeInterviewForm.result || undefined,
      });
      setCompleteInterviewForm({ interviewId: '', feedback: '', rating: '', result: '' });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to complete interview');
    }
  };

  const handleInterviewAction = async () => {
    setActionError(null);
    if (!interviewActionId) {
      setActionError('Interview ID is required.');
      return;
    }
    try {
      if (interviewAction === 'cancel') {
        await interviewMutations.cancel(interviewActionId);
      } else {
        await interviewMutations.markNoShow(interviewActionId);
      }
      setInterviewActionId('');
    } catch (err: any) {
      setActionError(err?.message || 'Interview action failed');
    }
  };

  const handleOfferAction = async () => {
    setActionError(null);
    if (!offerActionId) {
      setActionError('Offer ID is required.');
      return;
    }
    try {
      if (offerAction === 'send') {
        await offerMutations.send(offerActionId);
      } else if (offerAction === 'accept') {
        await offerMutations.accept(offerActionId);
      } else if (offerAction === 'reject') {
        await offerMutations.reject(offerActionId);
      } else {
        if (!offerVoidReason) {
          setActionError('Void reason is required.');
          return;
        }
        await offerMutations.void(offerActionId, { void_reason: offerVoidReason });
      }
      setOfferActionId('');
      setOfferVoidReason('');
    } catch (err: any) {
      setActionError(err?.message || 'Offer action failed');
    }
  };

  const handleBulkOfferSend = async () => {
    setActionError(null);
    const ids = bulkOfferIds.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) {
      setActionError('Provide offer ids.');
      return;
    }
    try {
      await offerMutations.bulkSend(ids, bulkOfferDelivery || undefined);
      setBulkOfferIds('');
    } catch (err: any) {
      setActionError(err?.message || 'Bulk send failed');
    }
  };

  const handleCreateOpening = async () => {
    setActionError(null);
    if (!newOpening.job_title) {
      setActionError('Job title is required.');
      return;
    }
    try {
      await jobOpeningMutations.create({
        job_title: newOpening.job_title,
        status: newOpening.status || 'open',
        company: newOpening.company || undefined,
        posting_date: newOpening.posting_date || undefined,
        expected_date: newOpening.expected_date || undefined,
        vacancies: newOpening.vacancies ? Number(newOpening.vacancies) : undefined,
        docstatus: 0,
      });
      setNewOpening({
        job_title: '',
        company: '',
        status: 'open',
        posting_date: '',
        expected_date: '',
        vacancies: '',
      });
    } catch (err: any) {
      setActionError(err?.message || 'Failed to create opening');
    }
  };

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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="space-y-3">
          <p className="text-white font-semibold">New Job Opening</p>
          <input
            type="text"
            placeholder="Job Title"
            value={newOpening.job_title}
            onChange={(e) => setNewOpening({ ...newOpening, job_title: e.target.value })}
            className="w-full bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Company"
              value={newOpening.company}
              onChange={(e) => setNewOpening({ ...newOpening, company: e.target.value })}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <select
              value={newOpening.status}
              onChange={(e) => setNewOpening({ ...newOpening, status: e.target.value })}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="date"
              value={newOpening.posting_date}
              onChange={(e) => setNewOpening({ ...newOpening, posting_date: e.target.value })}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <input
              type="date"
              value={newOpening.expected_date}
              onChange={(e) => setNewOpening({ ...newOpening, expected_date: e.target.value })}
              className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
          <input
            type="number"
            placeholder="Vacancies"
            value={newOpening.vacancies}
            onChange={(e) => setNewOpening({ ...newOpening, vacancies: e.target.value })}
            className="bg-slate-elevated border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
          />
          <button
            onClick={handleCreateOpening}
            className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
          >
            Create Opening
          </button>
        </div>

        <div className="space-y-3">
          <p className="text-white font-semibold">Interviews</p>
          <DataTable
            columns={[
              { key: 'job_applicant_name', header: 'Applicant', render: (item: any) => <span className="text-white">{item.job_applicant_name || item.job_applicant_id}</span> },
              { key: 'scheduled_at', header: 'Scheduled', render: (item: any) => <span className="text-slate-muted text-sm">{formatDate(item.scheduled_at)}</span> },
              { key: 'interviewer', header: 'Interviewer', render: (item: any) => <span className="text-slate-muted text-sm">{item.interviewer}</span> },
              { key: 'status', header: 'Status', render: (item: any) => <span className="text-slate-muted text-sm capitalize">{item.status || 'scheduled'}</span> },
            ]}
            data={(interviewList.items || []).map((item: any) => ({ ...item, id: item.id || `${item.job_applicant_id}-${item.scheduled_at}` }))}
            keyField="id"
            loading={interviewsLoading}
            emptyMessage="No interviews"
          />
        </div>
      </div>
      {actionError && <p className="text-red-400 text-sm">{actionError}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 bg-slate-card border border-slate-border rounded-xl p-4">
        <div className="space-y-3">
          <p className="text-white font-semibold">Applicant Actions</p>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Schedule Interview</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Applicant ID"
                value={scheduleForm.applicantId}
                onChange={(e) => setScheduleForm({ ...scheduleForm, applicantId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="datetime-local"
                value={scheduleForm.interview_date}
                onChange={(e) => setScheduleForm({ ...scheduleForm, interview_date: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Interviewer"
                value={scheduleForm.interviewer}
                onChange={(e) => setScheduleForm({ ...scheduleForm, interviewer: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Location"
                value={scheduleForm.location}
                onChange={(e) => setScheduleForm({ ...scheduleForm, location: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <input
              type="text"
              placeholder="Notes"
              value={scheduleForm.notes}
              onChange={(e) => setScheduleForm({ ...scheduleForm, notes: e.target.value })}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <button
              onClick={handleScheduleInterview}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Schedule Interview
            </button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Attach Offer to Applicant</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Applicant ID"
                value={makeOfferForm.applicantId}
                onChange={(e) => setMakeOfferForm({ ...makeOfferForm, applicantId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Offer ID"
                value={makeOfferForm.offerId}
                onChange={(e) => setMakeOfferForm({ ...makeOfferForm, offerId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <button
              onClick={handleMakeOffer}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Link Offer
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-white font-semibold">Interviews & Offers</p>
          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Create Interview</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Applicant ID"
                value={interviewForm.applicantId}
                onChange={(e) => setInterviewForm({ ...interviewForm, applicantId: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="datetime-local"
                value={interviewForm.scheduled_at}
                onChange={(e) => setInterviewForm({ ...interviewForm, scheduled_at: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Interviewer"
                value={interviewForm.interviewer}
                onChange={(e) => setInterviewForm({ ...interviewForm, interviewer: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="text"
                placeholder="Location"
                value={interviewForm.location}
                onChange={(e) => setInterviewForm({ ...interviewForm, location: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <select
              value={interviewForm.mode}
              onChange={(e) => setInterviewForm({ ...interviewForm, mode: e.target.value })}
              className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="in-person">In-person</option>
              <option value="remote">Remote</option>
              <option value="phone">Phone</option>
            </select>
            <button
              onClick={handleCreateInterview}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Create Interview
            </button>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Complete/Cancel Interview</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Interview ID"
                value={completeInterviewForm.interviewId}
                onChange={(e) => {
                  setCompleteInterviewForm({ ...completeInterviewForm, interviewId: e.target.value });
                  setInterviewActionId(e.target.value);
                }}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <input
                type="number"
                placeholder="Rating"
                value={completeInterviewForm.rating}
                onChange={(e) => setCompleteInterviewForm({ ...completeInterviewForm, rating: e.target.value })}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <input
              type="text"
              placeholder="Result (pass/fail)"
              value={completeInterviewForm.result}
              onChange={(e) => setCompleteInterviewForm({ ...completeInterviewForm, result: e.target.value })}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <textarea
              placeholder="Feedback"
              value={completeInterviewForm.feedback}
              onChange={(e) => setCompleteInterviewForm({ ...completeInterviewForm, feedback: e.target.value })}
              className="w-full bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCompleteInterview}
                className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
              >
                Complete Interview
              </button>
              <select
                value={interviewAction}
                onChange={(e) => setInterviewAction(e.target.value as 'cancel' | 'no-show')}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="cancel">Cancel</option>
                <option value="no-show">No-show</option>
              </select>
              <button
                onClick={handleInterviewAction}
                className="px-3 py-2 rounded-lg text-sm font-semibold border border-slate-border text-slate-muted hover:text-white"
              >
                Apply
              </button>
            </div>
          </div>

          <div className="bg-slate-elevated border border-slate-border rounded-lg p-3 space-y-2">
            <p className="text-sm text-white font-semibold">Offer Actions</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Offer ID"
                value={offerActionId}
                onChange={(e) => setOfferActionId(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <select
                value={offerAction}
                onChange={(e) => setOfferAction(e.target.value as 'send' | 'accept' | 'reject' | 'void')}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="send">Send</option>
                <option value="accept">Accept</option>
                <option value="reject">Reject</option>
                <option value="void">Void</option>
              </select>
            </div>
            {offerAction === 'void' && (
              <input
                type="text"
                placeholder="Void reason"
                value={offerVoidReason}
                onChange={(e) => setOfferVoidReason(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
            )}
            <button
              onClick={handleOfferAction}
              className="bg-teal-electric text-slate-deep px-3 py-2 rounded-lg text-sm font-semibold hover:bg-teal-glow transition-colors"
            >
              Run Offer Action
            </button>
            <div className="pt-2 space-y-2 border-t border-slate-border">
              <p className="text-xs text-slate-muted">Bulk send offers</p>
              <input
                type="text"
                placeholder="Offer IDs (comma-separated)"
                value={bulkOfferIds}
                onChange={(e) => setBulkOfferIds(e.target.value)}
                className="bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
              />
              <div className="flex gap-2">
                <select
                  value={bulkOfferDelivery}
                  onChange={(e) => setBulkOfferDelivery(e.target.value)}
                  className="flex-1 bg-slate-card border border-slate-border rounded-lg px-3 py-2 text-sm text-white"
                >
                  <option value="email">Email</option>
                  <option value="manual">Manual</option>
                </select>
                <button
                  onClick={handleBulkOfferSend}
                  className="px-3 py-2 rounded-lg text-sm font-semibold border border-slate-border text-slate-muted hover:text-white"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      {actionError && <p className="text-red-400 text-sm">{actionError}</p>}

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
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex gap-2 text-xs">
                  <button
                    onClick={(e) => { e.stopPropagation(); applicantMutations.screen(item.id).catch((err: any) => setActionError(err?.message || 'Screen failed')); }}
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Screen
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); applicantMutations.withdraw(item.id).catch((err: any) => setActionError(err?.message || 'Withdraw failed')); }}
                    className="px-2 py-1 rounded border border-red-500 text-red-300 hover:bg-red-500/10"
                  >
                    Withdraw
                  </button>
                </div>
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
            {
              key: 'actions',
              header: 'Actions',
              render: (item: any) => (
                <div className="flex flex-wrap gap-2 text-xs">
                  <button
                    onClick={(e) => { e.stopPropagation(); offerMutations.send(item.id).catch((err: any) => setActionError(err?.message || 'Send failed')); }}
                    className="px-2 py-1 rounded border border-teal-electric text-teal-electric hover:bg-teal-electric/10"
                  >
                    Send
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); offerMutations.accept(item.id).catch((err: any) => setActionError(err?.message || 'Accept failed')); }}
                    className="px-2 py-1 rounded border border-green-500 text-green-300 hover:bg-green-500/10"
                  >
                    Accept
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); offerMutations.reject(item.id).catch((err: any) => setActionError(err?.message || 'Reject failed')); }}
                    className="px-2 py-1 rounded border border-red-500 text-red-300 hover:bg-red-500/10"
                  >
                    Reject
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); offerMutations.void(item.id, { void_reason: 'Void from list' }).catch((err: any) => setActionError(err?.message || 'Void failed')); }}
                    className="px-2 py-1 rounded border border-slate-border text-slate-muted hover:bg-slate-elevated/50"
                  >
                    Void
                  </button>
                </div>
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
