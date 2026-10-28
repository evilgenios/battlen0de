"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowRight, LockKeyhole, MessageSquare, Send } from "lucide-react";
import { marketplaceApi } from "@/lib/api/marketplace";
import { useMarketplace } from "./MarketplaceProvider";
import { MarketplaceError } from "./MarketplaceShell";

export function ConversationPanel({
  initialConversation = "",
}: {
  initialConversation?: string;
}) {
  const { config } = useMarketplace();
  const threads = useSWR(
    "marketplace-conversations",
    marketplaceApi.conversations,
  );
  const [selected, setSelected] = useState(initialConversation);
  const active = selected || threads.data?.[0]?.id;
  const messages = useSWR(
    active ? ["marketplace-messages", active] : null,
    ([, id]) => marketplaceApi.messages(id),
    { refreshInterval: config?.messaging_enabled ? 8000 : 0 },
  );
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  async function send() {
    if (!active || busy || !body.trim()) return;
    setBusy(true);
    setError(undefined);
    try {
      await marketplaceApi.send(active, body);
      setBody("");
      await messages.mutate();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="mp-page-heading">
        <p className="mp-kicker">PRIVATE CONVERSATIONS</p>
        <h1>Keep the details in the conversation.</h1>
        <p>
          Listing inquiries stay between the buyer and seller. Structured offers
          and checkout are not enabled.
        </p>
      </div>
      {!config?.messaging_enabled && (
        <div className="mp-notice mb-6 flex items-start gap-3">
          <LockKeyhole size={18} className="mt-1 shrink-0 text-accent" />
          <span>
            New inquiries and replies are unavailable while the marketplace is
            in preview. Existing conversations remain readable by their
            participants.
          </span>
        </div>
      )}
      {threads.error ? (
        <MarketplaceError
          error={threads.error}
          retry={() => void threads.mutate()}
        />
      ) : threads.isLoading ? (
        <div className="mp-empty" role="status">
          Loading conversations…
        </div>
      ) : !threads.data?.length ? (
        <div className="mp-panel mp-empty">
          <MessageSquare size={32} className="text-accent" />
          <h2>Your conversations will live here.</h2>
          <p>
            When inquiries are enabled, contact a seller from their listing to
            start a private conversation.
          </p>
          <Link href="/marketplace" className="mp-button mt-5">
            Explore commanders <ArrowRight size={15} />
          </Link>
        </div>
      ) : (
        <div className="mp-panel mp-inbox">
          <nav className="mp-inbox-list" aria-label="Conversations">
            {threads.data.map((thread) => (
              <button
                key={thread.id}
                type="button"
                aria-pressed={active === thread.id}
                onClick={() => {
                  setSelected(thread.id);
                  setBody("");
                  setError(undefined);
                }}
              >
                <span className="mp-kicker">LISTING INQUIRY</span>
                <strong className="mt-2 block font-medium">
                  {thread.title}
                </strong>
              </button>
            ))}
          </nav>
          <section
            key={active}
            className="mp-messages"
            aria-label="Conversation messages"
          >
            <div className="border-b border-border pb-4">
              <h2 className="text-sm font-semibold">
                {threads.data.find((row) => row.id === active)?.title ??
                  "Conversation"}
              </h2>
              <p className="mt-2 text-[10px] text-muted-foreground">
                Never share login credentials or recovery information.
              </p>
            </div>
            {messages.error ? (
              <MarketplaceError error={messages.error} />
            ) : messages.isLoading ? (
              <p role="status" className="mp-copy">
                Loading messages…
              </p>
            ) : (
              <div
                className="flex max-h-[500px] flex-1 flex-col gap-4 overflow-y-auto"
                role="log"
                aria-live="polite"
              >
                {messages.data?.map((message) => (
                  <article
                    key={message.id}
                    className={`mp-message ${message.mine ? "mp-message-mine" : ""}`}
                  >
                    <span className="mb-1 block text-[9px] text-muted-foreground">
                      {message.mine ? "You" : "Other participant"}
                    </span>
                    {message.body}
                    <time dateTime={message.created_at}>
                      {new Date(message.created_at).toLocaleString()}
                    </time>
                  </article>
                ))}
              </div>
            )}
            {error ? <MarketplaceError error={error} /> : null}
            <form
              className="mt-auto flex items-end gap-3 border-t border-border pt-3"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <label className="mp-field !mt-0 flex-1">
                <span className="sr-only">Your reply</span>
                <textarea
                  required
                  maxLength={3000}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  disabled={!config?.messaging_enabled || busy}
                  placeholder={
                    config?.messaging_enabled
                      ? "Write a reply…"
                      : "Replies are not enabled"
                  }
                />
              </label>
              <button
                type="submit"
                className="mp-button mp-button-primary"
                disabled={!config?.messaging_enabled || busy || !body.trim()}
                aria-label="Send reply"
              >
                <Send size={16} />
              </button>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
