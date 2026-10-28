import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { ConversationPanel } from "@/components/marketplace/ConversationPanel";
export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<{ conversation?: string }>;
}) {
  const { conversation } = await searchParams;
  return (
    <MemberOnly>
      <ConversationPanel initialConversation={conversation} />
    </MemberOnly>
  );
}
