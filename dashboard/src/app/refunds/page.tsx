import type { Metadata } from 'next';
import { MarketingLegalPage, type LegalSection } from '@/components/marketing/MarketingLegalPage';

export const metadata: Metadata = {
  title: 'Refund Policy',
  description: 'Refund principles for paid BattleN0de access.',
};

const sections: LegalSection[] = [
  {
    title: 'When this policy applies',
    body: (
      <p>This policy applies only to payments made for BattleN0de access through an official sales or checkout channel. If no payment was made, there is no purchase amount to refund. Nothing in this policy reduces rights that cannot lawfully be waived.</p>
    ),
  },
  {
    title: 'Reviewable refund cases',
    body: (
      <p>Contact support if you believe you were charged more than once for the same order, paid for access that was never delivered, were charged an amount different from the confirmed order, or experienced another purchase problem caused by BattleN0de. We will review the transaction and available records.</p>
    ),
  },
  {
    title: 'Activated or consumed access',
    body: (
      <p>Where time-limited or otherwise consumable access has already been activated and used, a change of mind generally does not by itself create a refund entitlement unless applicable law requires otherwise or the purchase terms expressly say differently.</p>
    ),
  },
  {
    title: 'Third-party game issues',
    body: (
      <p>A game update, publisher policy change, game-account restriction, credential problem, network condition, or decision by a third-party service does not automatically make a BattleN0de purchase refundable. We will still consider whether BattleN0de failed to provide the access that was actually sold.</p>
    ),
  },
  {
    title: 'Suspended access and misuse',
    body: (
      <p>Access suspended or terminated for fraud, unauthorized sharing, deliberate plan-limit evasion, attacks on the service, chargeback abuse, or another material breach of the Terms is not normally eligible for a voluntary refund, subject to any rights that cannot legally be excluded.</p>
    ),
  },
  {
    title: 'How to request a review',
    body: (
      <p>Use the official BattleN0de support channel associated with your purchase. Include enough information to identify the transaction, the plan or access purchased, the date, and the problem. Do not post passwords, game tokens, device IDs, or other secret credentials in a public support channel.</p>
    ),
  },
  {
    title: 'Processing and policy updates',
    body: (
      <>
        <p>If a refund is approved, it will normally be returned through the original payment method where the payment provider supports that route. Processing time can depend on the payment provider.</p>
        <p>We may update this policy when the sales model, payment providers, or legal requirements change. The version shown here is the current policy.</p>
      </>
    ),
  },
];

export default function RefundPolicyPage() {
  return (
    <MarketingLegalPage
      eyebrow="Legal / Refunds"
      title="Refund Policy"
      intro="Clear principles for paid access without pretending the current dashboard has a self-service billing system that it does not yet have."
      sections={sections}
    />
  );
}
