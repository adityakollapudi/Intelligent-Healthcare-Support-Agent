// Screens whose backend services arrive in later phases. They show real structure and honest
// availability, never sample records or metrics.
import { Link } from "react-router-dom";

import { ChecklistLegend, READINESS_DISCLAIMER } from "../components/Checklist";
import { Alert, Button, EmptyState, FeatureUnavailable, PageHeader } from "../components/ui";
import { features } from "../lib/features";

export function ReadinessPage() {
  return (
    <>
      <PageHeader title="Prior authorization readiness" description="Check whether a document packet appears complete against a configured requirement set." />
      <Alert tone="info" title="Readiness is not approval">
        {READINESS_DISCLAIMER}
      </Alert>
      <FeatureUnavailable feature={features.readiness} />
      <section className="section card" aria-labelledby="legend-heading">
        <h2 id="legend-heading">What checklist statuses mean</h2>
        <ChecklistLegend />
      </section>
      <section className="section">
        <h2>Checklists</h2>
        <EmptyState title="No checklists yet">Checklists appear here after documents are analyzed and a readiness check is run.</EmptyState>
      </section>
    </>
  );
}

export function CasesPage() {
  return (
    <>
      <PageHeader
        title="Support cases"
        description="Ask a support agent for help and track your requests."
        actions={
          <Button disabled aria-describedby="new-case-reason">
            New case
          </Button>
        }
      />
      <p id="new-case-reason" className="muted small">
        Creating cases is disabled until the support-case service is connected (Phase {features.supportCases.phase}).
      </p>
      <FeatureUnavailable feature={features.supportCases} />
      <EmptyState title="No cases to show">Your cases will be listed here with their status and last update.</EmptyState>
    </>
  );
}

export function AgentPage() {
  return (
    <>
      <PageHeader title="Case queue" description="Unassigned cases and cases assigned to you, with escalation reasons and linked evidence." />
      <FeatureUnavailable feature={features.agentWorkspace} />
      <EmptyState title="Queue is empty">No case data is available until the case-management service is connected.</EmptyState>
    </>
  );
}

export function AdminPage() {
  return (
    <>
      <PageHeader title="Admin dashboard" description="Aggregate metrics, knowledge gaps and audit events from the synthetic prototype environment." />
      <FeatureUnavailable feature={features.adminDashboard}>
        <p className="muted small">No metrics are shown until real aggregates are available, so nothing on this page is estimated or sample data.</p>
      </FeatureUnavailable>
    </>
  );
}

export function ProviderWorkspacePage() {
  return (
    <>
      <PageHeader title="Provider workspace" description="Start an administrative task for a fictional prior authorization request." />
      <div className="tiles">
        <Link className="tile" to="/benefits">
          <span className="tile-title">Look up plan benefits</span>
          <span className="muted small">Available now</span>
        </Link>
        <Link className="tile" to="/chat">
          <span className="tile-title">Ask about requirements</span>
          <span className="muted small">Assistant arrives in Phase {features.chat.phase}</span>
        </Link>
        <Link className="tile" to="/documents">
          <span className="tile-title">Upload a document</span>
          <span className="muted small">Analysis arrives in Phase {features.documents.phase}</span>
        </Link>
        <Link className="tile" to="/readiness">
          <span className="tile-title">Check readiness</span>
          <span className="muted small">Arrives in Phase {features.readiness.phase}</span>
        </Link>
      </div>
    </>
  );
}
