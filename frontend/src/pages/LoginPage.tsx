import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { HOME_BY_ROLE } from "../app/navigation";
import { Alert, Button, TextField } from "../components/ui";
import { useSession } from "../features/auth/session";
import { describeError, isApiError } from "../lib/errors";

export function LoginPage() {
  const { status, user, signIn } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "signed_in" && user) return <Navigate to={HOME_BY_ROLE[user.role]} replace />;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const next: typeof errors = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = "Enter a valid email address.";
    if (password.length < 8) next.password = "Passwords are at least 8 characters.";
    setErrors(next);
    setFailure(null);
    if (Object.keys(next).length) return;

    setBusy(true);
    try {
      const me = await signIn(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      // Only same-app paths: "//host" would be a protocol-relative (cross-origin) URL.
      const safeFrom = from && from.startsWith("/") && !from.startsWith("//") && from !== "/login" ? from : null;
      navigate(safeFrom ?? HOME_BY_ROLE[me.role], { replace: true });
    } catch (error) {
      setPassword("");
      setFailure(
        isApiError(error) && error.status === 401 ? "Email or password is incorrect." : describeError(error).message,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <main className="login-card">
        <p className="wordmark wordmark-dark">IHSA</p>
        <h1>Sign in</h1>
        <p className="muted">
          Intelligent Healthcare Support Agent — an internship prototype using synthetic data. Not an Evernorth product.
        </p>
        {params.get("expired") === "1" && status !== "signed_in" && (
          <Alert tone="warning" title="Your session ended">
            Please sign in again to continue.
          </Alert>
        )}
        {failure && <Alert tone="danger" title="Sign-in failed">{failure}</Alert>}
        <form onSubmit={onSubmit} noValidate>
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            required
          />
          <div className="password-row">
            <TextField
              label="Password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
              required
            />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              aria-pressed={showPassword}
              onClick={() => setShowPassword((s) => !s)}
            >
              {showPassword ? "Hide password" : "Show password"}
            </button>
          </div>
          <Button type="submit" busy={busy} className="btn-block">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <p className="muted small">Demo accounts are created by the backend seed script; see backend/README.md.</p>
      </main>
    </div>
  );
}
