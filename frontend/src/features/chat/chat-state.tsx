// In-memory conversation state so the chat survives navigation (never persisted to browser storage;
// the server keeps the conversation and it can be reopened from "Recent conversations").
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { features } from "../../lib/features";
import { chatService } from "../../services";
import type { AnswerType, ChatRecord, Citation, EvidenceStatus, HistoryMessage, ProposedAction, ToolExecution } from "../../types/api";
import { useSession } from "../auth/session";

export const MAX_MESSAGE_LENGTH = 4000;

export interface ChatMessage {
  id: string;
  sender: "USER" | "ASSISTANT";
  text: string;
  answerType?: AnswerType | null;
  evidenceStatus?: EvidenceStatus | null;
  citations?: Citation[];
  proposedActions?: ProposedAction[];
  disclaimers?: string[];
  records?: ChatRecord[];
  toolExecutions?: ToolExecution[];
}

interface ChatValue {
  messages: ChatMessage[];
  sessionId: string | null;
  draft: string;
  setDraft: (value: string) => void;
  pending: boolean;
  error: unknown;
  unavailableNotice: boolean;
  send: () => Promise<void>;
  reset: () => void;
  openSession: (sessionId: string) => Promise<void>;
  sessionsVersion: number;
  available: boolean;
}

const ChatContext = createContext<ChatValue | null>(null);

export function validateMessage(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return "Type a question first.";
  if (trimmed.length > MAX_MESSAGE_LENGTH) return `Questions can be up to ${MAX_MESSAGE_LENGTH} characters.`;
  return null;
}

function fromHistory(m: HistoryMessage): ChatMessage {
  return {
    id: m.message_id,
    sender: m.sender,
    text: m.content,
    answerType: m.answer_type,
    evidenceStatus: m.evidence_status,
    citations: m.citations,
    proposedActions: m.proposed_actions,
    disclaimers: m.disclaimers,
    records: m.records ?? [],
    toolExecutions: m.tool_executions ?? [],
  };
}

export function ChatProvider({ children, available = features.chat.available }: { children: ReactNode; available?: boolean }) {
  const { user } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [unavailableNotice, setUnavailableNotice] = useState(false);
  const [sessionsVersion, setSessionsVersion] = useState(0);
  const inFlight = useRef<AbortController | null>(null);
  // Reused when the user retries a failed send, so the server treats it as the same message.
  const retryId = useRef<{ text: string; id: string } | null>(null);

  const reset = useCallback(() => {
    inFlight.current?.abort();
    retryId.current = null;
    setSessionId(null);
    setMessages([]);
    setDraft("");
    setError(null);
    setPending(false);
    setUnavailableNotice(false);
  }, []);

  // A different (or no) user must never see the previous user's conversation.
  useEffect(() => reset(), [user?.id, reset]);

  const send = useCallback(async () => {
    if (pending || validateMessage(draft)) return;
    if (!available) {
      setUnavailableNotice(true); // the draft is kept; nothing is sent or invented
      return;
    }
    const text = draft.trim();
    const clientMessageId = retryId.current?.text === text ? retryId.current.id : crypto.randomUUID();
    retryId.current = { text, id: clientMessageId };
    const controller = new AbortController();
    inFlight.current = controller;
    setPending(true);
    setError(null);
    setMessages((m) => [...m, { id: clientMessageId, sender: "USER", text }]);
    setDraft("");
    try {
      const response = await chatService.send(
        { session_id: sessionId, client_message_id: clientMessageId, message: text },
        controller.signal,
      );
      retryId.current = null;
      if (response.session_id !== sessionId) setSessionsVersion((v) => v + 1);
      setSessionId(response.session_id);
      setMessages((m) => [
        ...m,
        {
          id: response.message_id,
          sender: "ASSISTANT",
          text: response.answer_text,
          answerType: response.answer_type,
          evidenceStatus: response.evidence_status,
          citations: response.citations,
          proposedActions: response.proposed_actions,
          disclaimers: response.disclaimers,
          records: response.records ?? [],
          toolExecutions: response.tool_executions ?? [],
        },
      ]);
    } catch (err) {
      if (controller.signal.aborted) return;
      // Put the question back so the user can retry without retyping (same id → no duplicate on the server).
      setMessages((m) => m.filter((msg) => msg.id !== clientMessageId));
      setDraft(text);
      setError(err);
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setPending(false);
      }
    }
  }, [available, draft, pending, sessionId]);

  const openSession = useCallback(
    async (id: string) => {
      reset();
      setPending(true);
      try {
        const detail = await chatService.session(id);
        setSessionId(detail.session_id);
        setMessages(detail.messages.map(fromHistory));
      } catch (err) {
        setError(err);
      } finally {
        setPending(false);
      }
    },
    [reset],
  );

  const value = useMemo(
    () => ({
      messages, sessionId, draft, setDraft, pending, error, unavailableNotice, send, reset, openSession,
      sessionsVersion, available,
    }),
    [messages, sessionId, draft, pending, error, unavailableNotice, send, reset, openSession, sessionsVersion, available],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used inside ChatProvider");
  return value;
}
