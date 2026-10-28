"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FileText,
  LockKeyhole,
} from "lucide-react";
import {
  marketplaceApi,
  type Listing,
  type ListingInput,
} from "@/lib/api/marketplace";
import { money, strengthLabel } from "@/lib/marketplace/demo";
import { MarketplaceError } from "./MarketplaceShell";

const initial: ListingInput = {
  title: "",
  description: "",
  commander_name: "",
  commander_id: "",
  server: 1,
  strength: 0,
  commander_level: 1,
  collector_level: 0,
  airspace: 0,
  vip: 0,
  composition: "balanced",
  research: 0,
  price_cents: 100,
  currency: "USD",
  evidence: "",
};
const steps = [
  "Commander",
  "Military development",
  "Evidence & price",
  "Review",
];

export function ListingWizard({ id }: { id?: string }) {
  const { data, error, isLoading } = useSWR(
    id ? ["marketplace-own-listing", id] : null,
    ([, key]) => marketplaceApi.ownListing(key),
  );
  const profile = useSWR("marketplace-dashboard", marketplaceApi.dashboard);
  if (error) return <MarketplaceError error={error} />;
  if (isLoading)
    return (
      <div className="mp-empty" role="status">
        Loading your draft…
      </div>
    );
  if (data && !["draft", "paused"].includes(data.status))
    return (
      <div className="mp-notice">
        Only drafts and paused listings can be edited.{" "}
        <Link className="underline" href="/marketplace/dashboard">
          Return to your dashboard.
        </Link>
      </div>
    );
  return (
    <WizardForm
      key={data?.id ?? "new"}
      existing={data}
      canSubmit={Boolean(
        profile.data?.profile.seller_enabled &&
          !profile.data?.profile.restricted,
      )}
    />
  );
}

function WizardForm({
  existing,
  canSubmit,
}: {
  existing?: Listing;
  canSubmit: boolean;
}) {
  const [draft, setDraft] = useState<ListingInput>(
    existing
      ? {
          ...initial,
          ...existing,
          commander_id: existing.commander_id ?? "",
          evidence: existing.evidence ?? "",
        }
      : initial,
  );
  const [saved, setSaved] = useState(existing);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const form = useRef<HTMLFormElement>(null);
  const router = useRouter();
  const { mutate } = useSWRConfig();
  function update<K extends keyof ListingInput>(
    key: K,
    value: ListingInput[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  async function save(submit: boolean) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      // Whitelist fields: private response metadata must never be echoed into a write.
      const body = Object.fromEntries(
        Object.keys(initial).map((key) => [
          key,
          draft[key as keyof ListingInput],
        ]),
      ) as unknown as ListingInput;
      const row = await marketplaceApi.save(body, saved?.id, saved?.version);
      setSaved(row);
      if (submit) {
        const reviewed = await marketplaceApi.transition(row, "submit");
        setSaved(reviewed);
      }
      await mutate("marketplace-dashboard");
      router.push("/marketplace/dashboard/listings");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const number = (
    key: keyof ListingInput,
    label: string,
    min: number,
    max: number,
  ) => (
    <label className="mp-field">
      {label}
      <input
        required
        type="number"
        min={min}
        max={max}
        step="1"
        value={String(draft[key])}
        onChange={(e) => update(key, Number(e.target.value) as never)}
      />
    </label>
  );
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mp-page-heading">
        <p className="mp-kicker">
          SELLER WORKSPACE / {existing ? "EDIT LISTING" : "NEW LISTING"}
        </p>
        <h1>Every detail tells a story.</h1>
        <p>
          Build a clear, structured commander profile. Your listing stays
          private until it has been reviewed and public listings are enabled.
        </p>
      </div>
      <ol className="mp-steps">
        {steps.map((label, index) => (
          <li
            key={label}
            className={`mp-step ${index === step ? "mp-step-active" : ""}`}
            aria-current={index === step ? "step" : undefined}
          >
            <span>{index < step ? "✓" : `0${index + 1}`}</span>
            {label}
          </li>
        ))}
      </ol>
      <form
        ref={form}
        className="mp-panel p-5 sm:p-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (step < 3) setStep(step + 1);
          else void save(false);
        }}
      >
        <p className="mp-kicker">STEP 0{step + 1} / 04</p>
        <h2 className="mt-2 text-xl font-medium tracking-tight">
          {steps[step]}
        </h2>
        {step === 0 && (
          <div className="mp-form-grid">
            <label className="mp-field mp-wide">
              Listing title
              <input
                autoFocus
                required
                minLength={5}
                maxLength={100}
                value={draft.title}
                onChange={(e) => update("title", e.target.value)}
                placeholder="e.g. Ground-focused Commander · Server 32"
              />
            </label>
            <label className="mp-field">
              Commander name
              <input
                required
                minLength={2}
                maxLength={60}
                value={draft.commander_name}
                onChange={(e) => update("commander_name", e.target.value)}
              />
            </label>
            <label className="mp-field">
              Public commander ID
              <input
                required
                minLength={2}
                maxLength={40}
                pattern="[a-zA-Z0-9-]+"
                aria-label="Public commander ID"
                value={draft.commander_id}
                onChange={(e) => update("commander_id", e.target.value)}
              />
              <span className="text-[10px]">
                Public game identifier only. Never enter a login email or
                password.
              </span>
            </label>
            {number("server", "Server", 1, 10000)}
            {number("commander_level", "Commander level", 1, 200)}
            <label className="mp-field mp-wide">
              Commander overview
              <textarea
                required
                minLength={30}
                maxLength={5000}
                value={draft.description}
                onChange={(e) => update("description", e.target.value)}
                placeholder="Describe your military focus, notable development, and anything a reviewer should understand."
              />
            </label>
          </div>
        )}
        {step === 1 && (
          <div className="mp-form-grid">
            {number(
              "strength",
              "Total strength (full number)",
              0,
              100000000000,
            )}
            {number("collector_level", "Collector level", 0, 200)}
            {number("airspace", "Airspace", 0, 100000)}
            {number("vip", "VIP level", 0, 100)}
            <label className="mp-field">
              Military focus
              <select
                value={draft.composition}
                onChange={(e) =>
                  update(
                    "composition",
                    e.target.value as ListingInput["composition"],
                  )
                }
              >
                <option value="balanced">Combined arms</option>
                <option value="ground">Ground command</option>
                <option value="air">Air superiority</option>
              </select>
            </label>
            {number("research", "Research progress (%)", 0, 100)}
            <div className="mp-notice mp-wide mt-6">
              Enter seller-supplied statistics from information you are
              authorized to use. This form does not connect to your linked
              Warpath account.
            </div>
          </div>
        )}
        {step === 2 && (
          <div className="mp-form-grid">
            <label className="mp-field">
              Asking price (USD)
              <input
                required
                type="number"
                min="1"
                max="1000000"
                step="0.01"
                value={draft.price_cents / 100}
                onChange={(e) =>
                  update(
                    "price_cents",
                    Math.round(Number(e.target.value) * 100),
                  )
                }
              />
            </label>
            <label className="mp-field">
              Currency
              <input value="USD — US Dollar" readOnly />
            </label>
            <label className="mp-field mp-wide">
              Supporting evidence notes
              <textarea
                aria-label="Supporting evidence notes"
                aria-describedby="listing-evidence-help"
                maxLength={5000}
                value={draft.evidence}
                onChange={(e) => update("evidence", e.target.value)}
                placeholder="Describe the screens and dates that support your statistics. Evidence notes are visible only to you and reviewers."
              />
              <span id="listing-evidence-help" className="text-[10px]">
                At least 20 characters are needed to submit for review. Drafts
                may leave this blank.
              </span>
            </label>
            <div className="mp-notice mp-wide mt-5 flex items-start gap-3">
              <LockKeyhole className="mt-1 shrink-0 text-accent" size={18} />
              <span>
                File uploads are not enabled in this release. Never include
                credentials, app tokens, device identifiers, recovery codes, or
                private session information in evidence notes.
              </span>
            </div>
          </div>
        )}
        {step === 3 && (
          <div className="mt-6">
            <div className="rounded-xl border border-border bg-background p-5">
              <p className="mp-kicker">
                SERVER {draft.server} / {draft.composition}
              </p>
              <h3 className="mt-3 text-xl font-medium">{draft.title}</h3>
              <p className="mp-copy mt-3">{draft.description}</p>
              <dl className="mp-stat-grid">
                <div>
                  <dt>Strength</dt>
                  <dd>{strengthLabel(draft.strength)}</dd>
                </div>
                <div>
                  <dt>Collector</dt>
                  <dd>{draft.collector_level}</dd>
                </div>
                <div>
                  <dt>Price</dt>
                  <dd>{money(draft.price_cents)}</dd>
                </div>
              </dl>
            </div>
            <div className="mp-notice mt-5 flex gap-3">
              <FileText size={18} className="mt-1 shrink-0 text-accent" />
              <p>
                {canSubmit
                  ? "You can save a private draft or send this listing to the moderation queue. Approval does not publish it while the marketplace is in preview."
                  : "You can save a private draft. A platform administrator must approve your seller access before you can submit it for review."}
              </p>
            </div>
          </div>
        )}
        {error ? (
          <div className="mt-5">
            <MarketplaceError error={error} />
            {saved && (
              <p className="mt-3 text-xs text-muted-foreground">
                Your draft has been saved.{" "}
                <Link
                  className="underline"
                  href="/marketplace/dashboard/listings"
                >
                  Open your listings.
                </Link>
              </p>
            )}
          </div>
        ) : null}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-6">
          <button
            type="button"
            className="mp-back-link"
            disabled={busy}
            onClick={() =>
              step ? setStep(step - 1) : router.push("/marketplace/dashboard")
            }
          >
            <ArrowLeft size={14} />
            {step ? "Previous step" : "Cancel"}
          </button>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className={`mp-button ${step < 3 ? "mp-button-primary" : ""}`}
            >
              {busy ? "Saving…" : step < 3 ? "Continue" : "Save draft"}
              {step < 3 && <ArrowRight size={14} />}
            </button>
            {step === 3 && canSubmit && (
              <button
                type="button"
                disabled={busy || draft.evidence.trim().length < 20}
                className="mp-button mp-button-primary"
                onClick={() => void save(true)}
              >
                <Check size={15} /> Save & submit
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
