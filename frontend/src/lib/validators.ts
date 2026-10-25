// Lightweight runtime guards for backend responses (no schema library needed for this scope).
import {
  CLAIM_STATUSES,
  type BenefitsResponse,
  type ChatResponse,
  type ClaimDetail,
  type ClaimPage,
  type ClaimSummary,
  type HealthResponse,
  type LoginResponse,
  type MeResponse,
} from "../types/api";

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isStrOrNull = (v: unknown) => v === null || isStr(v);
const ROLES = ["MEMBER", "PROVIDER", "SUPPORT_AGENT", "ADMIN"];

export const isHealth = (v: unknown): v is HealthResponse =>
  isObj(v) && (v.status === "ok" || v.status === "degraded") && isObj(v.checks);

export const isLogin = (v: unknown): v is LoginResponse =>
  isObj(v) && isStr(v.access_token) && isObj(v.user) && ROLES.includes(v.user.role as string);

export const isMe = (v: unknown): v is MeResponse =>
  isObj(v) && isStr(v.id) && ROLES.includes(v.role as string) && Array.isArray(v.permissions);

export const isClaimSummary = (v: unknown): v is ClaimSummary =>
  isObj(v) &&
  isStr(v.claim_number) &&
  isStr(v.submission_date) &&
  isStr(v.last_status_change_at) &&
  (CLAIM_STATUSES as readonly string[]).includes(v.status as string) &&
  isStrOrNull(v.provider_name);

export const isClaimDetail = (v: unknown): v is ClaimDetail =>
  isClaimSummary(v) && isObj(v) && isStr(v.member_number) && isStrOrNull(v.status_description);

export const isClaimPage = (v: unknown): v is ClaimPage =>
  isObj(v) && Array.isArray(v.items) && v.items.every(isClaimSummary) && isStrOrNull(v.next_cursor);

export const isBenefits = (v: unknown): v is BenefitsResponse =>
  isObj(v) &&
  isStr(v.plan_code) &&
  isStr(v.plan_name) &&
  Array.isArray(v.benefits) &&
  v.benefits.every((b) => isObj(b) && isStr(b.benefit_category) && isStr(b.service_name) && typeof b.prior_auth_required === "boolean");

export const isChatResponse = (v: unknown): v is ChatResponse =>
  isObj(v) && isStr(v.session_id) && isStr(v.answer_text) && Array.isArray(v.citations) && isStr(v.evidence_status);
