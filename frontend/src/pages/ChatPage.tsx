import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { SourceCitationList } from "../components/SourceCitation";
import { ToolExecutionList, ToolRecords } from "../components/ToolRecords";
import { EVIDENCE_STATUS_META, MetaBadge } from "../components/status";
import { Alert, Button, ErrorState, PageHeader } from "../components/ui";
import { useSession } from "../features/auth/session";
import { MAX_MESSAGE_LENGTH, useChat, validateMessage, type ChatMessage } from "../features/chat/chat-state";
import { useRequest } from "../hooks/useRequest";
import { features } from "../lib/features";
import { formatDateTime, humanize } from "../lib/format";
import { chatService, supportCasesService } from "../services";
import { CASE_CATEGORIES, type CaseCategory, type CaseDetail, type CreateCaseRequest, type ProposedAction } from "../types/api";

const SUGGESTIONS: Record<string, string[]> = {
  MEMBER: [
    "How many physical therapy visits does my plan cover?",
    "What is the status of my claim SYN-CLM-2026-000101?",
    "What does the claim status pending information mean?",
    "How long do I have to appeal a denied claim?",
  ],
  PROVIDER: [
    "What documents are required for a lumbar MRI prior authorization?",
    "Within how many days must an in-network provider submit a claim?",
  ],
  default: ["How do I update my mailing address?", "What happens after a support case is created?"],
};

function proposalFrom(prefill: Record<string, unknown>): (CreateCaseRequest & { idempotency_key: string }) | null {
  const { category, summary, escalation_reason, related_session_id, idempotency_key } = prefill;
  if (typeof category !== "string" || !(CASE_CATEGORIES as readonly string[]).includes(category)) return null;
  if (typeof summary !== "string" || typeof idempotency_key !== "string") return null;
  return {
    category: category as CaseCategory,
    summary,
    escalation_reason: typeof escalation_reason === "string" ? escalation_reason : undefined,
    related_session_id: typeof related_session_id === "string" ? related_session_id : null,
    idempotency_key,
  };
}

/** The assistant only proposes a case. It's created when the user confirms, with the server-issued
 * idempotency key, so retries or double clicks can't create duplicates. */
function CreateCaseAction({ action }: { action: ProposedAction }) {
  const proposal = proposalFrom(action.prefill);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<CaseDetail | null>(null);

  if (!proposal) return <UnavailableAction label={action.label} />;
  if (created) {
    return (
      <Alert tone="success" title={`Support case ${created.case_number} created`}>
        Status: {humanize(created.status)}.{" "}
        <Link to={`/cases?case=${encodeURIComponent(created.case_id)}`}>View the case</Link>
      </Alert>
    );
  }
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      const { idempotency_key, ...body } = proposal;
      setCreated(await supportCasesService.create(body, idempotency_key)); // shown only after 201/200
      setOpen(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button variant="secondary" className="btn-sm" onClick={() => setOpen(true)}>
        {action.label}
      </Button>
      <ConfirmDialog
        open={open}
        title="Create a support case?"
        confirmLabel={error ? "Try again" : "Create case"}
        busy={busy}
        onCancel={() => setOpen(false)}
        onConfirm={() => void confirm()}
      >
        <p>A support agent will see these details. Nothing has been created yet.</p>
        <dl className="facts">
          <div>
            <dt>Category</dt>
            <dd>{humanize(proposal.category)}</dd>
          </div>
          {proposal.escalation_reason && (
            <div>
              <dt>Reason</dt>
              <dd>{humanize(proposal.escalation_reason)}</dd>
            </div>
          )}
        </dl>
        <p className="record-title">Summary</p>
        <p className="message-text">{proposal.summary}</p>
        {Boolean(error) && <ErrorState error={error} />}
      </ConfirmDialog>
    </>
  );
}

function UnavailableAction({ label }: { label: string }) {
  return (
    <span className="action-unavailable">
      <button type="button" className="btn btn-secondary btn-sm" disabled>
        {label}
      </button>
      <span className="muted small">Not available yet in this prototype</span>
    </span>
  );
}

function ActionButton({ action }: { action: ProposedAction }) {
  if (action.action_type === "VIEW_CLAIM" && action.available) {
    return (
      <Link className="btn btn-secondary btn-sm" to="/claims">
        {action.label}
      </Link>
    );
  }
  if (action.action_type === "VIEW_CASE" && action.available) {
    return (
      <Link className="btn btn-secondary btn-sm" to="/cases">
        {action.label}
      </Link>
    );
  }
  if (action.action_type === "CREATE_SUPPORT_CASE" && action.available && features.supportCases.available) {
    return <CreateCaseAction action={action} />;
  }
  // Every other action's backend arrives in a later phase: shown, but honestly disabled.
  return <UnavailableAction label={action.label} />;
}

/** FR-034. The rating is shown as recorded only after the backend confirms it. */
function AnswerFeedback({ messageId }: { messageId: string }) {
  const { can } = useSession();
  const [saved, setSaved] = useState<"HELPFUL" | "NOT_HELPFUL" | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  if (!can("feedback:create")) return null;
  const send = async (rating: "HELPFUL" | "NOT_HELPFUL") => {
    setBusy(true);
    setFailed(false);
    try {
      await chatService.feedback(messageId, rating);
      setSaved(rating);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="feedback" role="group" aria-label="Rate this answer">
      <span className="muted small">Was this helpful?</span>
      {(["HELPFUL", "NOT_HELPFUL"] as const).map((r) => (
        <button key={r} type="button" className="chip" aria-pressed={saved === r} disabled={busy} onClick={() => void send(r)}>
          {r === "HELPFUL" ? "👍 Yes" : "👎 No"}
        </button>
      ))}
      {saved && <span className="muted small" role="status">Thanks, your rating was recorded.</span>}
      {failed && <span className="field-error small" role="alert">Your rating wasn't saved. Please try again.</span>}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.sender === "USER";
  const limited = message.answerType === "INSUFFICIENT_EVIDENCE" || message.answerType === "UNSUPPORTED_REQUEST";
  return (
    <li className={`message ${isUser ? "message-user" : "message-assistant"} ${limited ? "message-limited" : ""}`}>
      <p className="message-sender">{isUser ? "You" : "Assistant"}</p>
      {/* Rendered as text: backend content is never interpreted as HTML. */}
      <p className="message-text">{message.text}</p>
      {message.evidenceStatus && message.evidenceStatus !== "NOT_APPLICABLE" && (
        <MetaBadge meta={EVIDENCE_STATUS_META[message.evidenceStatus]} />
      )}
      {message.toolExecutions && <ToolExecutionList executions={message.toolExecutions} />}
      {message.records && <ToolRecords records={message.records} />}
      {message.citations && <SourceCitationList citations={message.citations} />}
      {message.proposedActions && message.proposedActions.length > 0 && (
        <div className="message-actions">
          {message.proposedActions.map((a) => (
            <ActionButton key={a.action_type} action={a} />
          ))}
        </div>
      )}
      {message.disclaimers?.map((d) => (
        <p key={d} className="muted small">
          {d}
        </p>
      ))}
      {!isUser && <AnswerFeedback messageId={message.id} />}
    </li>
  );
}

function RecentConversations() {
  const chat = useChat();
  const list = useRequest((signal) => chatService.sessions(signal));
  useEffect(() => {
    void list.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when a new session is created
  }, [chat.sessionsVersion]);

  const { state } = list;
  return (
    <details className="recent" open>
      <summary>Recent conversations</summary>
      {state.status === "loading" && <p className="muted small">Loading…</p>}
      {state.status === "error" && <p className="field-error">Couldn't load conversations.</p>}
      {state.status === "success" && state.data.items.length === 0 && <p className="muted small">No conversations yet.</p>}
      {state.status === "success" && state.data.items.length > 0 && (
        <ul>
          {state.data.items.map((s) => (
            <li key={s.session_id}>
              <button
                type="button"
                className={`recent-item ${s.session_id === chat.sessionId ? "active" : ""}`}
                aria-current={s.session_id === chat.sessionId ? "true" : undefined}
                onClick={() => void chat.openSession(s.session_id)}
              >
                <span className="recent-title">{s.title}</span>
                <span className="muted small">{formatDateTime(s.last_message_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
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
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 160;
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }, [chat.messages.length]);

  const submit = () => {
    const invalid = validateMessage(chat.draft);
    // Show the validation message only for a rejected submit, not under the cleared composer afterwards.
    setTouched(Boolean(invalid));
    if (!invalid) void chat.send();
  };

  const suggestions = SUGGESTIONS[user?.role ?? ""] ?? SUGGESTIONS.default!;

  return (
    <div className="chat-layout">
      {chat.available && <RecentConversations />}
      <div className="chat-page">
        <PageHeader
          title="Assistant"
          description="Ask administrative questions about benefits, claims processes, documents and support. Answers come from synthetic plan documents and show their sources."
          actions={
            <Button variant="secondary" onClick={() => setConfirmReset(true)} disabled={chat.messages.length === 0 && !chat.draft}>
              New conversation
            </Button>
          }
        />
        {!chat.available && (
          <Alert tone="info" title={`AI answers arrive in Phase ${features.chat.phase}`}>
            The assistant service ({features.chat.endpoints.join(", ")}) isn't connected yet, so questions can't be answered.
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
              Working on it…
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
            disabled={chat.pending}
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
          The current conversation is cleared from this screen. It stays available under Recent conversations.
        </ConfirmDialog>
      </div>
    </div>
  );
}
