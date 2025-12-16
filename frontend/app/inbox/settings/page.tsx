'use client';

import { useState } from 'react';
import {
  Settings,
  Bell,
  Clock,
  User,
  Mail,
  MessageSquare,
  ToggleLeft,
  ToggleRight,
  Save,
  Globe,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SettingToggle {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

export default function InboxSettingsPage() {
  const [settings, setSettings] = useState<SettingToggle[]>([
    { id: 'desktop_notifications', label: 'Desktop Notifications', description: 'Show desktop notifications for new messages', enabled: true },
    { id: 'sound_alerts', label: 'Sound Alerts', description: 'Play sound when new message arrives', enabled: true },
    { id: 'email_notifications', label: 'Email Notifications', description: 'Receive email digest of unread conversations', enabled: false },
    { id: 'auto_assign', label: 'Auto-Assign to Me', description: 'Automatically assign conversations when you reply', enabled: true },
    { id: 'typing_indicator', label: 'Show Typing Indicator', description: 'Let customers see when you are typing', enabled: true },
    { id: 'read_receipts', label: 'Read Receipts', description: 'Show when you have read customer messages', enabled: false },
    { id: 'away_message', label: 'Away Message', description: 'Auto-reply when you are offline', enabled: false },
  ]);

  const [workingHours, setWorkingHours] = useState({
    enabled: true,
    start: '09:00',
    end: '18:00',
    timezone: 'Africa/Lagos',
    daysOff: ['Saturday', 'Sunday'],
  });

  const toggleSetting = (id: string) => {
    setSettings((prev) =>
      prev.map((s) => (s.id === id ? { ...s, enabled: !s.enabled } : s))
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-slate-500/10 border border-slate-500/30 flex items-center justify-center">
            <Settings className="w-5 h-5 text-slate-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Inbox Settings</h1>
            <p className="text-slate-muted text-sm">Configure your inbox preferences</p>
          </div>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors">
          <Save className="w-4 h-4" />
          Save Changes
        </button>
      </div>

      {/* Notification Settings */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Notifications & Alerts</h2>
        </div>
        <div className="space-y-4">
          {settings.slice(0, 3).map((setting) => (
            <div key={setting.id} className="flex items-center justify-between py-3 border-b border-slate-border/50 last:border-0">
              <div>
                <p className="text-white font-medium">{setting.label}</p>
                <p className="text-sm text-slate-muted">{setting.description}</p>
              </div>
              <button
                onClick={() => toggleSetting(setting.id)}
                className={cn('transition-colors', setting.enabled ? 'text-emerald-400' : 'text-slate-muted')}
              >
                {setting.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Conversation Settings */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="w-5 h-5 text-emerald-400" />
          <h2 className="text-lg font-semibold text-white">Conversation Behavior</h2>
        </div>
        <div className="space-y-4">
          {settings.slice(3).map((setting) => (
            <div key={setting.id} className="flex items-center justify-between py-3 border-b border-slate-border/50 last:border-0">
              <div>
                <p className="text-white font-medium">{setting.label}</p>
                <p className="text-sm text-slate-muted">{setting.description}</p>
              </div>
              <button
                onClick={() => toggleSetting(setting.id)}
                className={cn('transition-colors', setting.enabled ? 'text-emerald-400' : 'text-slate-muted')}
              >
                {setting.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Working Hours */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">Working Hours</h2>
          </div>
          <button
            onClick={() => setWorkingHours((prev) => ({ ...prev, enabled: !prev.enabled }))}
            className={cn('transition-colors', workingHours.enabled ? 'text-emerald-400' : 'text-slate-muted')}
          >
            {workingHours.enabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
          </button>
        </div>

        {workingHours.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-slate-muted mb-2">Start Time</label>
                <input
                  type="time"
                  value={workingHours.start}
                  onChange={(e) => setWorkingHours((prev) => ({ ...prev, start: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-2">End Time</label>
                <input
                  type="time"
                  value={workingHours.end}
                  onChange={(e) => setWorkingHours((prev) => ({ ...prev, end: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-muted mb-2">Timezone</label>
                <select
                  value={workingHours.timezone}
                  onChange={(e) => setWorkingHours((prev) => ({ ...prev, timezone: e.target.value }))}
                  className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                >
                  <option value="Africa/Lagos">Africa/Lagos (WAT)</option>
                  <option value="Europe/London">Europe/London (GMT)</option>
                  <option value="America/New_York">America/New_York (EST)</option>
                  <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-muted mb-2">Days Off</label>
              <div className="flex flex-wrap gap-2">
                {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day) => (
                  <button
                    key={day}
                    onClick={() => {
                      setWorkingHours((prev) => ({
                        ...prev,
                        daysOff: prev.daysOff.includes(day)
                          ? prev.daysOff.filter((d) => d !== day)
                          : [...prev.daysOff, day],
                      }));
                    }}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                      workingHours.daysOff.includes(day)
                        ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                        : 'bg-slate-elevated text-slate-muted hover:text-white'
                    )}
                  >
                    {day.slice(0, 3)}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Profile Settings */}
      <div className="bg-slate-card border border-slate-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <User className="w-5 h-5 text-violet-400" />
          <h2 className="text-lg font-semibold text-white">Agent Profile</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-muted mb-2">Display Name</label>
            <input
              type="text"
              defaultValue="Support Agent"
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-muted mb-2">Email</label>
            <input
              type="email"
              defaultValue="agent@company.com"
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm text-slate-muted mb-2">Default Signature</label>
            <textarea
              rows={3}
              defaultValue="Best regards,\nSupport Team"
              className="w-full bg-slate-elevated border border-slate-border rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
