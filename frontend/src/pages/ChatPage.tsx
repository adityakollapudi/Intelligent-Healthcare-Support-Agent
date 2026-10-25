import { useEffect, useRef, useState } from "react";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { SourceCitationList } from "../components/SourceCitation";
import { EVIDENCE_STATUS_META, MetaBadge } from "../components/status";
import { Alert, Button, ErrorState, PageHeader } from "../components/ui";
import { useSession } from "../features/auth/session";
import { MAX_MESSAGE_LENGTH, useChat, validateMessage, type ChatMessage } from "../features/chat/chat-state";
import { features } from "../lib/features";

const SUGGESTIONS: Record<string, string[]> = {
  MEMBER: ["What's the status of my latest claim?", "What does my plan cover for physical therapy?", "Which documents do I need for an MRI?"],
  PROVIDER: ["What documentation does a lumbar MRI request need?", "How do I prepare a prior authorization packet?"],
  default: ["How do I update my contact details?"],
};

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.sender === "USER";
  return (
    <li className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      <p className="message-sender">{isUser ? "You" : "Assistant"}</p>
      {/* Rendered as text: backend content is never interpreted as HTML. */}
      <p className="message-text">{message.text}</p>
      {message.evidenceStatus && <MetaBadge meta={EVIDENCE_STATUS_META[message.evidenceStatus]} />}
      {message.citations && <SourceCitationList citations={message.citations} />}
      {message.disclaimers?.map((d) => (
        <p key={d} className="muted small">
          {d}
        </p>
      ))}
    </li>
  );
}

export function ChatPage() {
  const { user } = useSession();
  const chat = useChat();
  const [touched, setTouched] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);
  const validation = touched ? validateMessage(chat.draft) : null;

  // Auto-scroll only if the reader is already near the bottom.
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 120;
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }, [chat.messages.length]);

  const submit = () => {
    setTouched(true);
    if (!validateMessage(chat.draft)) void chat.send();
  };

  const suggestions = SUGGESTIONS[user?.role ?? ""] ?? SUGGESTIONS.default!;

  return (
    <div className="chat-page">
      <PageHeader
        title="Assistant"
        description="Ask administrative questions about benefits, claims, documents and support. Answers will cite their sources."
        actions={
          <Button variant="secondary" onClick={() => setConfirmReset(true)} disabled={chat.messages.length === 0 && !chat.draft}>
            New conversation
          </Button>
        }
      />
      {!chat.available && (
        <Alert tone="info" title={`AI answers arrive in Phase ${features.chat.phase}`}>
          The assistant service ({features.chat.endpoints.join(", ")}) isn't connected yet, so questions can't be answered.
          You can still check claims and plan benefits from the menu.
        </Alert>
      )}

      <section className="chat-panel" aria-label="Conversation">
        {chat.messages.length === 0 ? (
          <div className="chat-empty">
            <p className="state-title">Start a conversation</p>
            <p className="muted">Try one of these:</p>
            <ul className="suggestions">
              {suggestions.map((s) => (
                <li key={s}>
                  <button type="button" className="chip" onClick={() => chat.setDraft(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol ref={listRef} className="messages" aria-live="polite">
            {chat.messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </ol>
        )}
        {chat.pending && (
          <p className="muted" role="status">
            Waiting for the assistant…
          </p>
        )}
      </section>

      {chat.unavailableNotice && (
        <Alert tone="warning" title="Not sent">
          Your question wasn't sent because the assistant service isn't connected yet. Your text has been kept.
        </Alert>
      )}
      {Boolean(chat.error) && <ErrorState error={chat.error} onRetry={() => void chat.send()} />}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-input"
          rows={3}
          value={chat.draft}
          maxLength={MAX_MESSAGE_LENGTH + 1}
          placeholder="Type your question…"
          aria-invalid={validation ? true : undefined}
          aria-describedby="chat-help"
          onChange={(e) => chat.setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <div className="composer-footer">
          <p id="chat-help" className={validation ? "field-error" : "muted small"}>
            {validation ?? `Enter to send · Shift+Enter for a new line · ${chat.draft.trim().length}/${MAX_MESSAGE_LENGTH}`}
          </p>
          <Button type="submit" busy={chat.pending}>
            Send
          </Button>
        </div>
      </form>

      <ConfirmDialog
        open={confirmReset}
        title="Start a new conversation?"
        confirmLabel="Start new"
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => {
          chat.reset();
          setConfirmReset(false);
        }}
      >
        The current conversation will be cleared from this screen.
      </ConfirmDialog>
    </div>
  );
}
