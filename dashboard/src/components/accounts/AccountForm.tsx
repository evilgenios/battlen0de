'use client';

import { useState } from 'react';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { describeError } from '@/components/ui/ErrorState';
import { createAccount } from '@/lib/api/accounts';
import type { AccountCreateRequest } from '@/lib/api/types';

interface FormState {
  label: string;
  linked_email: string;
  platform: number;
  app_uid: string;
  app_token: string;
  device_id: string;
  app_id: string;
  pack_name: string;
  channel_id: string;
  app_version: string;
  package_version: string;
  // advanced / optional — defaults mirror
  // service/app/core/warpath/credentials.py's WarpathCredentials defaults.
  profile_uid: string;
  device_model: string;
  os_type: string;
  os_version: string;
  os_language: string;
  pack_language: string;
  timezone: string;
  env_id: string;
  net_route_type: string;
  net_route_info: string;
  client_ip: string;
  game_id: string;
  server_ip: string;
  server_port: string;
  login_timeout: string;
}

const PLATFORM_OPTIONS = [
  { value: 22, label: 'PC' },
  { value: 15, label: 'iOS' },
  { value: 21, label: 'Android' },
  { value: 0, label: 'Self' },
];

function initialState(): FormState {
  return {
    label: '',
    linked_email: '',
    platform: 22,
    app_uid: '',
    app_token: '',
    device_id: '',
    app_id: '',
    pack_name: '',
    channel_id: '',
    app_version: '',
    package_version: '',
    profile_uid: '',
    device_model: 'win',
    os_type: 'win',
    os_version: '',
    os_language: 'ENG',
    pack_language: 'ENG',
    timezone: '0',
    env_id: '',
    net_route_type: '0',
    net_route_info: '',
    client_ip: '',
    game_id: '10048',
    server_ip: '34.8.3.236',
    server_port: '10000',
    login_timeout: '30',
  };
}

/** Mirrors WarpathCredentials.validation_errors() (see credentials.py) —
 * checked here too so a user finds out about a missing field immediately
 * instead of only after Connect returns a 422. */
function validate(form: FormState): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {};
  const required: Exclude<keyof FormState, 'platform'>[] = [
    'label', 'app_uid', 'app_token', 'device_id',
    'app_id', 'pack_name', 'channel_id', 'app_version', 'package_version',
  ];
  for (const field of required) {
    if (!form[field].trim()) errors[field] = 'Required';
  }
  if (form.linked_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.linked_email)) {
    errors.linked_email = 'Not a valid email address';
  }
  if (form.platform === 22 && form.os_type.trim() !== 'win' && form.os_type.trim() !== 'pc') {
    errors.os_type = "PC credentials require 'win' (or 'pc')";
  }
  for (const field of ['profile_uid', 'timezone', 'net_route_type', 'server_port', 'login_timeout'] as const) {
    if (form[field] !== '' && Number.isNaN(Number(form[field]))) {
      errors[field] = 'Must be a number';
    }
  }
  return errors;
}

function toCreateRequest(form: FormState): AccountCreateRequest {
  return {
    label: form.label.trim(),
    linked_email: form.linked_email.trim() || null,
    app_uid: form.app_uid.trim(),
    app_token: form.app_token,
    device_id: form.device_id,
    platform: form.platform,
    profile_uid: form.profile_uid ? Number(form.profile_uid) : null,
    device_metadata: {
      app_id: form.app_id.trim(),
      pack_name: form.pack_name.trim(),
      channel_id: form.channel_id.trim(),
      app_version: form.app_version.trim(),
      package_version: form.package_version.trim(),
      device_model: form.device_model.trim(),
      os_type: form.os_type.trim(),
      os_version: form.os_version.trim(),
      os_language: form.os_language.trim(),
      pack_language: form.pack_language.trim(),
      timezone: Number(form.timezone || 0),
      env_id: form.env_id.trim(),
      net_route_type: Number(form.net_route_type || 0),
      net_route_info: form.net_route_info.trim(),
      client_ip: form.client_ip.trim(),
      game_id: form.game_id.trim(),
      server_ip: form.server_ip.trim(),
      server_port: Number(form.server_port || 10000),
      login_timeout: Number(form.login_timeout || 30),
    },
  };
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-foreground">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

const inputClass =
  'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/50';

export function AccountForm() {
  const { user } = useAuthSession();
  if (user?.role !== 'admin') return null;
  return <AdminAccountForm  />;
}

function AdminAccountForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const router = useRouter();
  const toast = useToast();

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const validationErrors = validate(form);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      toast.error('Check the form', 'Some required fields are missing or invalid.');
      return;
    }

    setSubmitting(true);
    try {
      const account = await createAccount(toCreateRequest(form));
      toast.success('Account created', `${account.label} was added.`);
      router.push(`/accounts/${account.id}`);
    } catch (error) {
      toast.error('Could not create account', describeError(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <Card>
        <CardHeader title="Account identity" description="How this account appears in the dashboard." />
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Label *" error={errors.label}>
            <input
              className={inputClass}
              value={form.label}
              onChange={(e) => set('label', e.target.value)}
              placeholder="e.g. Main Account"
              autoComplete="off"
            />
          </Field>
          <Field label="Linked email" error={errors.linked_email}>
            <input
              className={inputClass}
              type="email"
              value={form.linked_email}
              onChange={(e) => set('linked_email', e.target.value)}
              placeholder="optional"
              autoComplete="off"
            />
          </Field>
          <Field label="Platform *">
            <select
              className={inputClass}
              value={form.platform}
              onChange={(e) => {
                const platform = Number(e.target.value);
                set('platform', platform);
                if (platform === 22 && !form.os_type) set('os_type', 'win');
              }}
            >
              {PLATFORM_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Profile UID" error={errors.profile_uid}>
            <input
              className={inputClass}
              value={form.profile_uid}
              onChange={(e) => set('profile_uid', e.target.value)}
              placeholder="optional"
              inputMode="numeric"
              autoComplete="off"
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader
          title="Warpath credentials"
          description="From the SDK session used to link this account. Never shown again after saving."
        />
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="App UID *" error={errors.app_uid}>
            <input
              className={inputClass}
              value={form.app_uid}
              onChange={(e) => set('app_uid', e.target.value)}
              autoComplete="off"
            />
          </Field>
          <div />
          <Field label="App Token *" error={errors.app_token}>
            <input
              className={inputClass}
              type="password"
              value={form.app_token}
              onChange={(e) => set('app_token', e.target.value)}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Device ID *" error={errors.device_id}>
            <input
              className={inputClass}
              type="password"
              value={form.device_id}
              onChange={(e) => set('device_id', e.target.value)}
              autoComplete="new-password"
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader
          title="Client/session metadata"
          description="Required for the login handshake — from the same client session as the credentials above."
        />
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="App ID *" error={errors.app_id}>
            <input className={inputClass} value={form.app_id} onChange={(e) => set('app_id', e.target.value)} />
          </Field>
          <Field label="Pack Name *" error={errors.pack_name}>
            <input className={inputClass} value={form.pack_name} onChange={(e) => set('pack_name', e.target.value)} />
          </Field>
          <Field label="Channel ID *" error={errors.channel_id}>
            <input className={inputClass} value={form.channel_id} onChange={(e) => set('channel_id', e.target.value)} />
          </Field>
          <Field label="App Version *" error={errors.app_version}>
            <input
              className={inputClass}
              value={form.app_version}
              onChange={(e) => set('app_version', e.target.value)}
              placeholder="e.g. 14.20.0000"
            />
          </Field>
          <Field label="Package Version *" error={errors.package_version}>
            <input
              className={inputClass}
              value={form.package_version}
              onChange={(e) => set('package_version', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <button
          type="button"
          onClick={() => setAdvancedOpen((open) => !open)}
          className="flex w-full items-center gap-2 px-5 py-4 text-left text-sm font-semibold text-foreground"
        >
          {advancedOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Advanced connection settings
          <span className="ml-auto text-xs font-normal text-muted-foreground">optional — sensible defaults applied</span>
        </button>
        {advancedOpen && (
          <CardContent className="grid gap-4 border-t border-border sm:grid-cols-2">
            <Field label="Device model">
              <input className={inputClass} value={form.device_model} onChange={(e) => set('device_model', e.target.value)} />
            </Field>
            <Field label="OS type" error={errors.os_type}>
              <input className={inputClass} value={form.os_type} onChange={(e) => set('os_type', e.target.value)} />
            </Field>
            <Field label="OS version">
              <input className={inputClass} value={form.os_version} onChange={(e) => set('os_version', e.target.value)} />
            </Field>
            <Field label="OS language">
              <input className={inputClass} value={form.os_language} onChange={(e) => set('os_language', e.target.value)} />
            </Field>
            <Field label="Pack language">
              <input className={inputClass} value={form.pack_language} onChange={(e) => set('pack_language', e.target.value)} />
            </Field>
            <Field label="Timezone offset" error={errors.timezone}>
              <input className={inputClass} value={form.timezone} onChange={(e) => set('timezone', e.target.value)} inputMode="numeric" />
            </Field>
            <Field label="Env ID">
              <input className={inputClass} value={form.env_id} onChange={(e) => set('env_id', e.target.value)} />
            </Field>
            <Field label="Net route type" error={errors.net_route_type}>
              <input className={inputClass} value={form.net_route_type} onChange={(e) => set('net_route_type', e.target.value)} inputMode="numeric" />
            </Field>
            <Field label="Net route info">
              <input className={inputClass} value={form.net_route_info} onChange={(e) => set('net_route_info', e.target.value)} />
            </Field>
            <Field label="Client IP">
              <input className={inputClass} value={form.client_ip} onChange={(e) => set('client_ip', e.target.value)} />
            </Field>
            <Field label="Game ID">
              <input className={inputClass} value={form.game_id} onChange={(e) => set('game_id', e.target.value)} />
            </Field>
            <Field label="Server IP">
              <input className={inputClass} value={form.server_ip} onChange={(e) => set('server_ip', e.target.value)} />
            </Field>
            <Field label="Server port" error={errors.server_port}>
              <input className={inputClass} value={form.server_port} onChange={(e) => set('server_port', e.target.value)} inputMode="numeric" />
            </Field>
            <Field label="Login timeout (seconds)" error={errors.login_timeout}>
              <input className={inputClass} value={form.login_timeout} onChange={(e) => set('login_timeout', e.target.value)} inputMode="numeric" />
            </Field>
          </CardContent>
        )}
      </Card>

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={() => router.push('/accounts')} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={submitting}>
          Add account
        </Button>
      </div>
    </form>
  );
}
