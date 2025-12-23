'use client';

import { useState, useMemo } from 'react';
import {
  FileText,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  Copy,
  Check,
  Mail,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useSupportCannedResponses } from '@/hooks/useApi';
import { Button, FilterInput, PageHeader } from '@/components/ui';

export default function InboxSignaturesPage() {
  const [search, setSearch] = useState('');
  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Use canned responses with category='signature' for email signatures
  const {
    data,
    error,
    isLoading,
    mutate: refresh,
  } = useSupportCannedResponses({
    category: 'signature',
  });

  const signatures = useMemo(() => data?.items ?? data?.data ?? [], [data?.items, data?.data]);

  // Filter locally for search
  const filteredSignatures = useMemo(() => {
    if (!search) return signatures;
    const searchLower = search.toLowerCase();
    return signatures.filter(
      (s: any) =>
        s.title?.toLowerCase().includes(searchLower) ||
        s.content?.toLowerCase().includes(searchLower)
    );
  }, [signatures, search]);

  const copyToClipboard = async (content: string, id: number) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Clipboard API not available
    }
  };

  // Strip HTML tags for preview
  const stripHtml = (html: string) => {
    const tmp = typeof document !== 'undefined' ? document.createElement('div') : null;
    if (tmp) {
      tmp.innerHTML = html;
      return tmp.textContent || tmp.innerText || '';
    }
    return html.replace(/<[^>]*>/g, '');
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-muted">
        <AlertTriangle className="w-12 h-12 mb-4 text-rose-400" />
        <p className="text-lg text-rose-400 mb-4">Failed to load signatures</p>
        <Button
          onClick={() => refresh()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-foreground transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/inbox/settings"
        className="inline-flex items-center gap-2 text-sm text-slate-muted hover:text-foreground transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to Settings
      </Link>

      {/* Header */}
      <PageHeader
        title="Email Signatures"
        subtitle="Signature templates for email replies"
        icon={FileText}
      />

      {/* Info banner */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Mail className="w-5 h-5 text-blue-400 mt-0.5" />
          <div>
            <p className="text-sm text-blue-400 font-medium">Managing Signatures</p>
            <p className="text-sm text-slate-muted mt-1">
              Email signatures are stored as canned responses with category &quot;signature&quot;.
              To add or edit signatures, visit the Support Canned Responses page.
            </p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <FilterInput
          type="text"
          placeholder="Search signatures..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-md"
        />
      </div>

      {/* Signatures Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
        </div>
      ) : filteredSignatures.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-muted bg-slate-card border border-slate-border rounded-xl">
          <FileText className="w-12 h-12 mb-4 opacity-50" />
          <p>{search ? 'No signatures match your search' : 'No signatures available'}</p>
          <p className="text-xs mt-2">
            Create signatures in Support → Canned Responses with category &quot;signature&quot;
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSignatures.map((signature: any) => (
            <div
              key={signature.id}
              className="bg-slate-card border border-slate-border rounded-xl overflow-hidden hover:border-slate-muted transition-colors"
            >
              <div className="flex items-center justify-between p-4 border-b border-slate-border bg-slate-elevated/50">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-violet-500/10 text-violet-400">
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <h3 className="font-medium text-foreground">{signature.title}</h3>
                </div>
                <Button
                  onClick={() => copyToClipboard(signature.content || '', signature.id)}
                  className="p-1.5 text-slate-muted hover:text-foreground hover:bg-slate-elevated rounded-lg transition-colors"
                  title="Copy to clipboard"
                >
                  {copiedId === signature.id ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </Button>
              </div>

              <div className="p-4">
                {/* Preview as plain text */}
                <p className="text-sm text-slate-muted line-clamp-4">
                  {stripHtml(signature.content || 'No content')}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Count */}
      {!isLoading && filteredSignatures.length > 0 && (
        <p className="text-sm text-slate-muted text-center">
          Showing {filteredSignatures.length} signature{filteredSignatures.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}
