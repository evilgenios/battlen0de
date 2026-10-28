import type { Metadata } from 'next';
import { MarketingLegalPage, type LegalSection } from '@/components/marketing/MarketingLegalPage';

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Terms governing access to and use of BattleN0de.',
};

const sections: LegalSection[] = [
  {
    title: 'Agreement to these terms',
    body: (
      <>
        <p>These Terms of Service apply when you activate access, create or use a BattleN0de login, link a game account, purchase access where paid access is offered, or otherwise use the service.</p>
        <p>By using BattleN0de, you confirm that you have read and accepted these Terms together with the Privacy Policy and, for paid access, the Refund Policy. If you do not agree, do not use the service.</p>
      </>
    ),
  },
  {
    title: 'What BattleN0de is',
    body: (
      <>
        <p>BattleN0de is an independent third-party web service that provides account monitoring, production views, operational controls, event history, and related account-management tools for Warpath players.</p>
        <p>BattleN0de is not owned by, affiliated with, sponsored by, endorsed by, or operated by Lilith Games or the publishers of Warpath. Warpath and any related third-party services remain governed by their own terms, rules, technical restrictions, and availability.</p>
      </>
    ),
  },
  {
    title: 'Your account and security',
    body: (
      <>
        <p>You are responsible for the accuracy of information you provide and for protecting your BattleN0de login, activation or recovery tokens, browser sessions, and any device from which you access the service.</p>
        <p>Do not share access in a way that defeats your assigned plan or account limits, and do not use another person&apos;s BattleN0de profile or linked game account without authorization. Tell the official support channel promptly if you believe access has been compromised.</p>
      </>
    ),
  },
  {
    title: 'Access grants and plan limits',
    body: (
      <>
        <p>Access may be provisioned through an invitation, activation token, recovery token, operator-created account, or another official method made available by BattleN0de. Activation and recovery tokens are intended for the recipient and may be single-use or time-limited.</p>
        <p>Individual Node is designed for one linked Warpath account. Alliance Node is the multi-account control surface. Account, concurrent-session, and active-account limits may also be applied server-side to a user or workspace. You may not bypass or artificially evade those limits.</p>
      </>
    ),
  },
  {
    title: 'Orders, fees, and paid access',
    body: (
      <>
        <p>If paid access is offered, the applicable plan, price, currency, duration, included limits, and renewal behavior will be shown or confirmed through the official sales or checkout channel before the transaction is completed.</p>
        <p>BattleN0de does not treat an access purchase as automatically recurring unless the purchase flow explicitly says so. Payment processors may apply their own terms. Refund requests are handled under the Refund Policy and any non-waivable rights provided by applicable law.</p>
      </>
    ),
  },
  {
    title: 'Authority to connect game accounts',
    body: (
      <>
        <p>You may only link or operate a Warpath account that you own or are authorized to manage. By submitting credentials or a verification code, you instruct BattleN0de to establish and maintain the connection needed to provide the features you request.</p>
        <p>You are responsible for determining whether your use of third-party game accounts, automation, remote sessions, or related features complies with the rules that apply to those third-party services.</p>
      </>
    ),
  },
  {
    title: 'Acceptable use',
    body: (
      <>
        <p>You must not attack, disrupt, overload, scrape, probe, or attempt to bypass the security of BattleN0de; obtain data or credentials belonging to another user; distribute malicious code; impersonate staff; resell or redistribute access without written permission; or use the service for unlawful activity.</p>
        <p>You must also not reverse engineer or circumvent technical protections except to the extent a right to do so cannot lawfully be restricted.</p>
      </>
    ),
  },
  {
    title: 'Service operation and changes',
    body: (
      <>
        <p>BattleN0de depends on hosted infrastructure, networks, and third-party game behavior that can change without notice. Features may be unavailable during maintenance, security work, capacity events, upstream changes, or failures outside our reasonable control.</p>
        <p>We may modify, add, limit, pause, or retire functionality when reasonably necessary to maintain security, reliability, compliance, or product development. We do not promise that every feature will remain compatible with every future Warpath update.</p>
      </>
    ),
  },
  {
    title: 'Suspension and termination',
    body: (
      <>
        <p>You may stop using the service at any time. We may restrict, suspend, or terminate access where reasonably necessary to protect users, infrastructure, third parties, or our legal interests, including where access is obtained fraudulently, security controls are bypassed, plan limits are deliberately evaded, or these Terms are materially breached.</p>
        <p>Ending access does not erase obligations or provisions that by their nature should continue, including provisions relating to payments, intellectual property, misuse, disclaimers, and liability.</p>
      </>
    ),
  },
  {
    title: 'No guaranteed game outcome',
    body: (
      <>
        <p>BattleN0de is provided on an available basis. To the maximum extent permitted by applicable law, we do not guarantee uninterrupted availability, error-free operation, compatibility with every game version or device, or any particular in-game result.</p>
        <p>Game actions may depend on network timing and upstream responses. The interface is designed to expose uncertainty where it is known rather than represent an unconfirmed command as successful. Nothing in these Terms excludes or limits a responsibility that cannot lawfully be excluded or limited.</p>
      </>
    ),
  },
  {
    title: 'Product materials and feedback',
    body: (
      <>
        <p>BattleN0de&apos;s original website, software, interface, documentation, branding, and other product materials are protected by applicable intellectual-property laws. Third-party names, game assets, and marks remain the property of their respective owners.</p>
        <p>If you voluntarily provide suggestions or product feedback, you allow us to use that feedback to improve the service without an obligation to compensate you, while you retain ownership of material that was already yours.</p>
      </>
    ),
  },
  {
    title: 'Updates and contact',
    body: (
      <>
        <p>We may revise these Terms as the product, access model, or legal requirements change. The current version will be published on this page with an updated date. Material changes may also be communicated through the service or the official support channel where appropriate.</p>
        <p>For questions about these Terms, use the official BattleN0de support channel associated with your access or purchase.</p>
      </>
    ),
  },
];

export default function TermsPage() {
  return (
    <MarketingLegalPage
      eyebrow="Legal / Terms"
      title="Terms of Service"
      intro="The rules for using BattleN0de, written for the product that actually exists — independent, account-bound, cloud-hosted, and intentionally fail-closed."
      sections={sections}
    />
  );
}
