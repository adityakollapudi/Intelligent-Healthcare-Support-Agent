// In-memory conversation state so the chat survives navigation (never persisted to storage).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { features } from "../../lib/features";
import { chatService } from "../../services";
import type { Citation, EvidenceStatus, ProposedAction } from "../../types/api";
import { useSession } from "../auth/session";

export const MAX_MESSAGE_LENGTH = 4000;

export interface ChatMessage {
  id: string;
  sender: "USER" | "ASSISTANT";
  text: string;
  evidenceStatus?: EvidenceStatus;
  citations?: Citation[];
  proposedActions?: ProposedAction[];
  disclaimers?: string[];
}

interface ChatValue {
  messages: ChatMessage[];
  draft: string;
  setDraft: (value: string) => void;
  pending: boolean;
  error: unknown;
  unavailableNotice: boolean;
  send: () => Promise<void>;
  reset: () => void;
  available: boolean;
}

const ChatContext = createContext<ChatValue | null>(null);

export function validateMessage(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return "Type a question first.";
  if (trimmed.length > MAX_MESSAGE_LENGTH) return `Questions can be up to ${MAX_MESSAGE_LENGTH} characters.`;
  return null;
}

export function ChatProvider({ children, available = features.chat.available }: { children: ReactNode; available?: boolean }) {
  const { user } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [unavailableNotice, setUnavailableNotice] = useState(false);
  const sessionId = useRef<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    inFlight.current?.abort();
    sessionId.current = null;
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
    const clientMessageId = crypto.randomUUID();
    const controller = new AbortController();
    inFlight.current = controller;
    setPending(true);
    setError(null);
    setMessages((m) => [...m, { id: clientMessageId, sender: "USER", text }]);
    setDraft("");
    try {
      const response = await chatService.send(
        { session_id: sessionId.current, client_message_id: clientMessageId, message: text },
        controller.signal,
      );
      sessionId.current = response.session_id;
      setMessages((m) => [
        ...m,
        {
          id: response.message_id,
          sender: "ASSISTANT",
          text: response.answer_text,
          evidenceStatus: response.evidence_status,
          citations: response.citations,
          proposedActions: response.proposed_actions,
          disclaimers: response.disclaimers,
        },
      ]);
    } catch (err) {
      if (controller.signal.aborted) return;
      // Put the question back so the user can retry without retyping.
      setMessages((m) => m.filter((msg) => msg.id !== clientMessageId));
      setDraft(text);
      setError(err);
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setPending(false);
      }
    }
  }, [available, draft, pending]);

  const value = useMemo(
    () => ({ messages, draft, setDraft, pending, error, unavailableNotice, send, reset, available }),
    [messages, draft, pending, error, unavailableNotice, send, reset, available],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used inside ChatProvider");
  return value;
}
