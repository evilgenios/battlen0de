import type { Metadata } from 'next';
import { MarketingLegalPage, type LegalSection } from '@/components/marketing/MarketingLegalPage';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'How BattleN0de handles account, session, game, and service data.',
};

const sections: LegalSection[] = [
  {
    title: 'Scope',
    body: (
      <p>This Privacy Policy explains how BattleN0de handles information when you visit the public site, use a dashboard login, activate access, link a Warpath account, connect a live game session, or use account-management features.</p>
    ),
  },
  {
    title: 'Information you provide',
    body: (
      <>
        <p>Depending on how your access is provisioned, we may process your email address, account label, activation or recovery information, support communications, and other information you intentionally submit.</p>
        <p>When you link a Warpath account, the service may receive a linked email address, game UID or profile UID, device and client metadata, app token, device ID, and the verification information needed to complete the link.</p>
      </>
    ),
  },
  {
    title: 'Sensitive game credentials',
    body: (
      <>
        <p>Saved app tokens and device IDs are encrypted before they are stored. The normal account response objects used by the dashboard do not contain those stored secret values.</p>
        <p>Credentials are decrypted only inside the server-side connection path when they are needed to establish a requested game session. Relinking replaces saved credentials without displaying the previous secret values in the browser.</p>
      </>
    ),
  },
  {
    title: 'Service and game-state data',
    body: (
      <p>To provide dashboard features, BattleN0de may process account status, connection state, profile information, unit or army state, map or base observations, production lines, active actions, command observations, account snapshots, diagnostics, and event history received from or derived from the connected game session.</p>
    ),
  },
  {
    title: 'Login and security data',
    body: (
      <p>We process password hashes, encrypted administrator authenticator secrets, role and account status, session identifiers, anti-CSRF tokens, session timestamps, authentication versions, rate-limit records, connection errors, and security-relevant events to authenticate users, protect accounts, enforce access boundaries, and investigate failures or abuse. Detailed administrator audit records may also contain the request peer address and user-agent string associated with a security or administrative action.</p>
    ),
  },
  {
    title: 'How information is used',
    body: (
      <>
        <p>Information is used to provide and secure the service, maintain live account sessions, display requested account state, enforce account and session limits, keep audit history, troubleshoot failures, support users, prevent abuse, and improve product reliability.</p>
        <p>BattleN0de does not sell your personal data to advertisers.</p>
      </>
    ),
  },
  {
    title: 'Who can access data',
    body: (
      <>
        <p>Regular dashboard members are restricted to linked accounts they own. Authorized service administrators may have broader operator access where required for support, security, maintenance, or platform administration.</p>
        <p>Infrastructure and service providers may process limited information on our behalf where needed to host, operate, secure, or deliver BattleN0de. Third-party services also process information under their own policies when you interact with them directly.</p>
      </>
    ),
  },
  {
    title: 'Retention and deletion',
    body: (
      <>
        <p>Data is kept for as long as reasonably needed to provide access, maintain security and auditability, resolve disputes, comply with applicable obligations, or operate the service. Retention periods can differ by data type. Detailed administrator security-audit records are currently configured for a 180-day retention window unless the operator changes that policy within the documented bounded range.</p>
        <p>Deleting a linked game account removes the active account record and associated live data that is configured to cascade with it. Certain audit events are intentionally designed to survive account deletion with the direct account reference removed so that security and operational history is not silently erased.</p>
      </>
    ),
  },
  {
    title: 'Your choices',
    body: (
      <p>You can stop using BattleN0de, disconnect or remove linked accounts through available controls, and contact the official support channel to ask about access, correction, or deletion of personal information where those rights apply. Some records may need to be retained where required for security, legal compliance, or legitimate audit purposes.</p>
    ),
  },
  {
    title: 'Third-party service and policy changes',
    body: (
      <>
        <p>BattleN0de is independent of Lilith Games. Linking a Warpath account does not change the game publisher&apos;s own collection or use of information.</p>
        <p>This policy may be updated as the product, infrastructure, or legal requirements change. The latest version and update date will remain available on this page.</p>
      </>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <MarketingLegalPage
      eyebrow="Legal / Privacy"
      title="Privacy Policy"
      intro="What BattleN0de processes, why it is needed, and where the account boundary sits."
      sections={sections}
    />
  );
}
