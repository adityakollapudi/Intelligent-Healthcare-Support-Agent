import { Link } from "react-router-dom";

export function AccessDeniedPage() {
  return (
    <section className="status-page">
      <h1>You don't have access to this page</h1>
      <p className="muted">Your account's role doesn't include this screen. If you think this is a mistake, contact support.</p>
      <Link className="btn btn-primary" to="/">
        Go to my home page
      </Link>
    </section>
  );
}

export function NotFoundPage() {
  return (
    <section className="status-page">
      <h1>We couldn't find that page</h1>
      <p className="muted">The address may be mistyped, or the page may not exist.</p>
      <Link className="btn btn-primary" to="/">
        Go to my home page
      </Link>
    </section>
  );
}
