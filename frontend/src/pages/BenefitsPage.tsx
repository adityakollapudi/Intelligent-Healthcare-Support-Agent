import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, TextField } from "../components/ui";
import { useSession } from "../features/auth/session";
import { useRequest } from "../hooks/useRequest";
import { isApiError } from "../lib/errors";
import { formatDate, humanize } from "../lib/format";
import { benefitsService } from "../services";
import type { BenefitItem, BenefitsResponse } from "../types/api";

export const PLAN_CODE_PATTERN = /^SYN-PLAN-[A-Z0-9-]{2,20}$/;

const notListed = <span className="muted">Not listed</span>;

function BenefitRow({ b }: { b: BenefitItem }) {
  return (
    <tr>
      <td data-label="Service">
        <strong>{b.service_name}</strong>
        {b.limitations && <p className="muted small">{b.limitations}</p>}
      </td>
      <td data-label="In network">{b.in_network_cost_share ?? notListed}</td>
      <td data-label="Out of network">{b.out_of_network_cost_share ?? notListed}</td>
      <td data-label="Visit limit">{b.visit_limit ?? notListed}</td>
      <td data-label="Prior auth">
        {b.prior_auth_required ? (
          <StatusBadge tone="warning" icon="⚠" label="Listed as required" />
        ) : (
          <StatusBadge tone="neutral" icon="–" label="Not listed" />
        )}
      </td>
      <td data-label="Source">
        {b.source ? `${b.source.document_title} v${b.source.document_version}` : <span className="muted">Not linked yet</span>}
      </td>
    </tr>
  );
}

function PlanView({ plan, onCategory, category }: { plan: BenefitsResponse; category: string; onCategory: (c: string) => void }) {
  const [categories, setCategories] = useState<string[]>([]);
  useEffect(() => {
    // Options come from the unfiltered response so the filter never offers empty categories.
    if (!category) setCategories([...new Set(plan.benefits.map((b) => b.benefit_category))]);
  }, [plan, category]);

  const grouped = plan.benefits.reduce<Record<string, BenefitItem[]>>((acc, b) => {
    (acc[b.benefit_category] ??= []).push(b);
    return acc;
  }, {});

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h2>{plan.plan_name}</h2>
          <p className="muted mono small">{plan.plan_code}</p>
        </div>
        <p className="muted small">
          Plan year {plan.plan_year} · {formatDate(plan.effective_start)} – {plan.effective_end ? formatDate(plan.effective_end) : "no end date"}
        </p>
      </div>
      <div className="field field-inline">
        <label htmlFor="category">Benefit category</label>
        <select id="category" value={category} onChange={(e) => onCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {humanize(c)}
            </option>
          ))}
        </select>
      </div>
      {plan.benefits.length === 0 ? (
        <EmptyState title="No benefit entries">This plan record has no entries for the selected category.</EmptyState>
      ) : (
        Object.entries(grouped).map(([cat, items]) => (
          <section key={cat} className="benefit-group">
            <h3>{humanize(cat)}</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Service</th>
                    <th scope="col">In network</th>
                    <th scope="col">Out of network</th>
                    <th scope="col">Visit limit</th>
                    <th scope="col">Prior authorization</th>
                    <th scope="col">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((b) => (
                    <BenefitRow key={b.service_name} b={b} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}
      <p className="muted small">
        Synthetic plan record. "Not listed" means the record has no value; it isn't a coverage decision. Source documents are
        linked once the knowledge base is connected (Phase 4).
      </p>
    </article>
  );
}

export function BenefitsPage() {
  const { user, can } = useSession();
  const ownPlan = user?.member?.plan_code ?? null;
  const canSearchAny = can("benefits:read:any");
  const [planCode, setPlanCode] = useState<string | null>(ownPlan);
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const request = useRequest((signal, code: string, cat: string) => benefitsService.get(code, cat || undefined, signal));

  useEffect(() => {
    if (planCode) void request.run(planCode, category);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run is stable
  }, [planCode, category]);

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const code = input.trim().toUpperCase();
    if (!PLAN_CODE_PATTERN.test(code)) {
      setInputError("Use a plan code like SYN-PLAN-GOLD-01.");
      return;
    }
    setInputError(null);
    setCategory("");
    setPlanCode(code);
  };

  const { state } = request;
  return (
    <>
      <PageHeader
        title="Plan benefits"
        description={canSearchAny ? "Look up plan-level benefit terms for any active synthetic plan." : "Benefit terms for your plan, from the plan record."}
      />
      {canSearchAny && (
        <form className="inline-form section" onSubmit={onSearch} noValidate>
          <TextField label="Plan code" hint="e.g. SYN-PLAN-GOLD-01" value={input} onChange={(e) => setInput(e.target.value)} error={inputError} spellCheck={false} />
          <Button type="submit" busy={state.status === "loading"}>
            Look up plan
          </Button>
        </form>
      )}
      {!planCode && !canSearchAny && (
        <EmptyState title="No plan on your account">Your account isn't linked to a plan record.</EmptyState>
      )}
      {!planCode && canSearchAny && <EmptyState title="Enter a plan code to see its benefits" />}
      <div aria-live="polite">
        {state.status === "loading" && <LoadingState label="Loading plan benefits…" />}
        {state.status === "error" &&
          (isApiError(state.error) && state.error.isNotFound ? (
            <Alert tone="warning" title="Plan not found">
              No active plan with that code is available to you.
            </Alert>
          ) : (
            <ErrorState error={state.error} onRetry={() => planCode && void request.run(planCode, category)} />
          ))}
        {state.status === "success" && <PlanView plan={state.data} category={category} onCategory={setCategory} />}
      </div>
    </>
  );
}
