'use client';

import { useState } from 'react';
import { useBanks } from '@/hooks/useApi';
import { AlertTriangle, Landmark, Search, CheckCircle, XCircle, Building2 } from 'lucide-react';
import { paymentsApi } from '@/lib/api';

export default function GatewayBanksPage() {
  const [search, setSearch] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [selectedBank, setSelectedBank] = useState('');
  const [resolving, setResolving] = useState(false);
  const [resolveResult, setResolveResult] = useState<{
    account_name: string;
    account_number: string;
    bank_code: string;
  } | null>(null);
  const [resolveError, setResolveError] = useState('');

  const { data, isLoading, error } = useBanks({ country: 'nigeria' });
  const banks: any[] = Array.isArray((data as any)?.banks)
    ? (data as any).banks
    : Array.isArray((data as any)?.results)
      ? (data as any).results
      : Array.isArray(data)
        ? (data as any)
        : [];

  const filteredBanks = banks.filter((bank: any) =>
    bank.name.toLowerCase().includes(search.toLowerCase()) ||
    bank.code.includes(search)
  ) || [];

  const handleResolve = async () => {
    if (!selectedBank || accountNumber.length !== 10) {
      return;
    }
    setResolving(true);
    setResolveResult(null);
    setResolveError('');

    try {
      const result = await paymentsApi.resolveAccount({ account_number: accountNumber, bank_code: selectedBank });
      setResolveResult(result);
    } catch (err: any) {
      setResolveError(err.message || 'Could not resolve account');
    } finally {
      setResolving(false);
    }
  };

  const selectedBankInfo = banks.find((b: any) => b.code === selectedBank);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400">Failed to load banks</p>
        </div>
      )}
      <div className="flex items-center gap-2">
        <Landmark className="w-5 h-5 text-teal-electric" />
        <h1 className="text-xl font-semibold text-white">Banks & NUBAN Lookup</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account Resolution */}
        <div className="bg-slate-800/50 border border-slate-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Search className="w-5 h-5 text-teal-electric" />
            Account Name Lookup
          </h2>
          <p className="text-slate-muted text-sm mb-4">
            Verify a Nigerian bank account by entering the account number and selecting the bank.
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-muted mb-1">Bank</label>
              <select
                value={selectedBank}
              onChange={(e) => { setSelectedBank(e.target.value); setResolveResult(null); setResolveError(''); }}
              className="input-field w-full"
            >
              <option value="">Select a bank</option>
                {banks.map((bank: any) => (
                  <option key={bank.code} value={bank.code}>{bank.name}</option>
                ))}
            </select>
            </div>

            <div>
              <label className="block text-sm text-slate-muted mb-1">Account Number (NUBAN)</label>
              <input
                type="text"
                value={accountNumber}
                onChange={(e) => { setAccountNumber(e.target.value.replace(/\D/g, '').slice(0, 10)); setResolveResult(null); setResolveError(''); }}
                className="input-field w-full font-mono"
                placeholder="0123456789"
                maxLength={10}
              />
              <p className="text-xs text-slate-muted mt-1">10-digit NUBAN account number</p>
            </div>

            <button
              onClick={handleResolve}
              disabled={resolving || !selectedBank || accountNumber.length !== 10}
              className="w-full px-4 py-2 rounded-lg bg-teal-electric text-slate-950 font-semibold hover:bg-teal-electric/90 disabled:opacity-50 transition-colors"
            >
              {resolving ? 'Verifying...' : 'Verify Account'}
            </button>

            {resolveResult && (
              <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-green-400 mb-2">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">Account Verified</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-slate-muted">Account Name:</span>
                    <span className="text-white ml-2 font-medium">{resolveResult.account_name}</span>
                  </div>
                  <div>
                    <span className="text-slate-muted">Account Number:</span>
                    <span className="text-white ml-2 font-mono">{resolveResult.account_number}</span>
                  </div>
                  <div>
                    <span className="text-slate-muted">Bank:</span>
                    <span className="text-white ml-2">{selectedBankInfo?.name || resolveResult.bank_code}</span>
                  </div>
                </div>
              </div>
            )}

            {resolveError && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-red-400">
                  <XCircle className="w-5 h-5" />
                  <span>{resolveError}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bank Directory */}
        <div className="bg-slate-800/50 border border-slate-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-teal-electric" />
            Bank Directory
          </h2>

          <div className="mb-4">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field w-full"
              placeholder="Search banks by name or code..."
            />
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric"></div>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto space-y-1 pr-2">
              {filteredBanks.length === 0 ? (
                <p className="text-slate-muted text-center py-4">No banks found</p>
              ) : (
                filteredBanks.map((bank: any) => (
                  <button
                    key={bank.code}
                    onClick={() => { setSelectedBank(bank.code); setResolveResult(null); setResolveError(''); }}
                    className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                      selectedBank === bank.code
                        ? 'bg-teal-electric/20 border border-teal-electric/50'
                        : 'bg-slate-900/50 hover:bg-slate-700/50 border border-transparent'
                    }`}
                  >
                    <div>
                      <div className={`text-sm font-medium ${selectedBank === bank.code ? 'text-teal-electric' : 'text-white'}`}>
                        {bank.name}
                      </div>
                      <div className="text-xs text-slate-muted">
                        {bank.type && <span className="capitalize">{bank.type}</span>}
                      </div>
                    </div>
                    <span className="font-mono text-xs text-slate-muted bg-slate-800 px-2 py-1 rounded">
                      {bank.code}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-slate-border">
            <p className="text-xs text-slate-muted">
              Total: {data?.banks?.length || 0} banks
            </p>
          </div>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-2">What is NUBAN?</h3>
          <p className="text-xs text-slate-muted">
            Nigeria Uniform Bank Account Number (NUBAN) is a 10-digit unique bank account identification system used by all Nigerian banks.
          </p>
        </div>
        <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-2">Account Verification</h3>
          <p className="text-xs text-slate-muted">
            Verify account details before making transfers to ensure funds are sent to the correct recipient.
          </p>
        </div>
        <div className="bg-slate-800/50 border border-slate-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-2">Supported Banks</h3>
          <p className="text-xs text-slate-muted">
            We support all CBN-licensed commercial banks, microfinance banks, and mobile money operators in Nigeria.
          </p>
        </div>
      </div>
    </div>
  );
}
