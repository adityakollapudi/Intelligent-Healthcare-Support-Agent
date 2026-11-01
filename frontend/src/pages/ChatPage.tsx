import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { SourceCitationList } from "../components/SourceCitation";
import { ToolExecutionList, ToolRecords } from "../components/ToolRecords";
import { EVIDENCE_STATUS_META, MetaBadge } from "../components/status";
import { Alert, Button, ErrorState, PageHeader } from "../components/ui";
import { ANSWER_LANGUAGES, CHAT_TEXT, QUICK_ACTIONS, WELCOME } from "../features/chat/chat-i18n";
import { useSession } from "../features/auth/session";
import { MAX_MESSAGE_LENGTH, useChat, validateMessage, type ChatMessage } from "../features/chat/chat-state";
import { useRequest } from "../hooks/useRequest";
import { useWordReveal } from "../hooks/useWordReveal";
import { features } from "../lib/features";
import { formatDateTime, humanize } from "../lib/format";
import { chatService, supportCasesService } from "../services";
import { CASE_CATEGORIES, type CaseCategory, type CaseDetail, type ChatRecord, type CreateCaseRequest, type Language, type ProposedAction } from "../types/api";

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

/** Choices offered by the assistant; picking one sends its message through the normal chat path. */
function GuidedOptions({ records }: { records: ChatRecord[] }) {
  const chat = useChat();
  const options = records.flatMap((r) => (r.kind === "suggestions" ? r.data.options : []));
  if (options.length === 0) return null;
  return (
    <ul className="suggestions">
      {options.map((o) => {
        const label = o.label[chat.language] ?? o.label.en;
        return (
          <li key={o.message + label}>
            <button type="button" className="chip" disabled={chat.pending} onClick={() => void chat.send({ label, message: o.message })}>
              {label}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Copy and translate. The original answer stays available, and identifiers are never changed. */
function MessageTools({ message, onTranslated }: { message: ChatMessage; onTranslated: (text: string, disclaimers: string[], complete: boolean) => void }) {
  const chat = useChat();
  const t = CHAT_TEXT[chat.language];
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
    } catch {
      setFailed(true);
    }
  };
  const translate = async (language: Language) => {
    setBusy(true);
    setFailed(false);
    try {
      const result = await chatService.translate(message.id, language);
      onTranslated(result.text, result.disclaimers, result.complete);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="message-tools" role="group" aria-label={t.answerTools}>
      <button type="button" className="chip" onClick={() => void copy()}>
        {copied ? t.copied : t.copy}
      </button>
      {ANSWER_LANGUAGES.map((l) => (
        <button key={l.code} type="button" className="chip" disabled={busy} onClick={() => void translate(l.code)}>
          {l.action}
        </button>
      ))}
      {failed && <span className="field-error small" role="alert">{t.toolFailed}</span>}
    </div>
  );
}

function MessageBubble({ message, onReveal }: { message: ChatMessage; onReveal: () => void }) {
  const chat = useChat();
  const isUser = message.sender === "USER";
  const [translated, setTranslated] = useState<{ text: string; disclaimers: string[]; complete: boolean } | null>(null);
  const { shown, done } = useWordReveal(message.text, Boolean(message.reveal), onReveal);
  const t = CHAT_TEXT[chat.language];
  const limited = message.answerType === "INSUFFICIENT_EVIDENCE" || message.answerType === "UNSUPPORTED_REQUEST";
  return (
    <li className={`message ${isUser ? "message-user" : "message-assistant"} ${limited ? "message-limited" : ""}`}>
      <p className="message-sender">
        {isUser ? t.you : t.assistant}
        {message.createdAt && <time className="muted small" dateTime={message.createdAt}> · {formatDateTime(message.createdAt)}</time>}
      </p>
      {/* Rendered as text: backend content is never interpreted as HTML. */}
      {/* Screen readers get the whole answer once, not every word as it appears. */}
      <p className="message-text" aria-hidden={!done}>
        {translated?.text ?? shown}
        {!done && <span className="reveal-caret" />}
      </p>
      {!done && <p className="sr-only">{message.text}</p>}
      {done && message.evidenceStatus && message.evidenceStatus !== "NOT_APPLICABLE" && (
        <MetaBadge meta={EVIDENCE_STATUS_META[message.evidenceStatus]} />
      )}
      {translated && !translated.complete && <p className="muted small">{t.partlyEnglish}</p>}
      {done && message.toolExecutions && <ToolExecutionList executions={message.toolExecutions} />}
      {done && message.records && <GuidedOptions records={message.records} />}
      {done && message.records && <ToolRecords records={message.records} />}
      {done && message.citations && <SourceCitationList citations={message.citations} />}
      {done && message.proposedActions && message.proposedActions.length > 0 && (
        <div className="message-actions">
          {message.proposedActions.map((a) => (
            <ActionButton key={a.action_type} action={a} />
          ))}
        </div>
      )}
      {done && (translated?.disclaimers ?? message.disclaimers)?.map((d) => (
        <p key={d} className="muted small">
          {d}
        </p>
      ))}
      {done && !isUser && <MessageTools message={message} onTranslated={(text, disclaimers, complete) => setTranslated({ text, disclaimers, complete })} />}
      {done && !isUser && <AnswerFeedback messageId={message.id} />}
    </li>
  );
}

/** The first thing a customer sees: a greeting and the things they can do. */
function WelcomePanel() {
  const chat = useChat();
  const { user } = useSession();
  const navigate = useNavigate();
  const role = user?.role ?? "MEMBER";
  return (
    <div className="chat-welcome">
      <p className="welcome-text">{WELCOME[role][chat.language]}</p>
      <ul className="quick-actions">
        {QUICK_ACTIONS[role].map((a) => (
          <li key={a.id}>
            <button
              type="button"
              className="quick-action"
              disabled={chat.pending}
              onClick={() => (a.path ? navigate(a.path) : void chat.send({ label: a.label[chat.language], message: a.message ?? "" }))}
            >
              {a.label[chat.language]}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LanguageSelector() {
  const chat = useChat();
  return (
    <select
      className="language-select"
      aria-label={CHAT_TEXT[chat.language].languageLabel}
      value={chat.language}
      onChange={(e) => chat.setLanguage(e.target.value as Language)}
    >
      {ANSWER_LANGUAGES.map((l) => (
        <option key={l.code} value={l.code} lang={l.code}>
          {l.name}
        </option>
      ))}
    </select>
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
  const chat = useChat();
  const t = CHAT_TEXT[chat.language];
  const [touched, setTouched] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);
  const validation = touched ? validateMessage(chat.draft) : null;

  // Auto-scroll only if the reader is already near the bottom.
  const followLatest = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 160;
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }, []);
  useEffect(followLatest, [chat.messages.length, followLatest]);

  const submit = () => {
    const invalid = validateMessage(chat.draft);
    // Show the validation message only for a rejected submit, not under the cleared composer afterwards.
    setTouched(Boolean(invalid));
    if (!invalid) void chat.send();
  };

  return (
    <div className="chat-layout">
      {chat.available && <RecentConversations />}
      <div className="chat-page">
        <PageHeader
          title={t.title}
          description={t.description}
          actions={
            <>
              <LanguageSelector />
              <Button variant="secondary" onClick={() => setConfirmReset(true)} disabled={chat.messages.length === 0 && !chat.draft}>
                {t.newConversation}
              </Button>
            </>
          }
        />
        {!chat.available && (
          <Alert tone="info" title={`AI answers arrive in Phase ${features.chat.phase}`}>
            The assistant service ({features.chat.endpoints.join(", ")}) isn't connected yet, so questions can't be answered.
          </Alert>
        )}

        <section className="chat-panel" aria-label={t.conversation}>
          {chat.messages.length === 0 ? (
            <WelcomePanel />
          ) : (
            <ol ref={listRef} className="messages" aria-live="polite">
              {chat.messages.map((m) => (
                <MessageBubble key={m.id} message={m} onReveal={followLatest} />
              ))}
            </ol>
          )}
          {chat.pending && (
            <p className="typing-indicator muted" role="status">
              <span className="typing-dots" aria-hidden="true" /> {t.typing}
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
            placeholder={t.placeholder}
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
              {validation ?? `${t.composerHelp} · ${chat.draft.trim().length}/${MAX_MESSAGE_LENGTH}`}
            </p>
            <Button type="submit" busy={chat.pending}>
              {t.send}
            </Button>
          </div>
        </form>

        <ConfirmDialog
          open={confirmReset}
          title={t.clearTitle}
          confirmLabel={t.clearConfirm}
          onCancel={() => setConfirmReset(false)}
          onConfirm={() => {
            chat.reset();
            setConfirmReset(false);
          }}
        >
          {t.clearBody}
        </ConfirmDialog>
      </div>
    </div>
  );
}
