// Administrators add members, providers and support agents, and see every account.
// The form stays on the same role after saving, so several accounts can be added in a row.
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader, TextField } from "../components/ui";
import { useRequest } from "../hooks/useRequest";
import { formatDateTime } from "../lib/format";
import { adminService } from "../services";
import type { ManagedRole, UserFormOptions } from "../types/api";

const ROLE_LABELS: Record<string, string> = {
  MEMBER: "Member (customer)",
  PROVIDER: "Provider",
  SUPPORT_AGENT: "Support agent",
  ADMIN: "Administrator",
};
const CREATABLE: ManagedRole[] = ["MEMBER", "PROVIDER", "SUPPORT_AGENT"];
const MIN_PASSWORD = 12;

function CreateUserForm({ options, onCreated }: { options: UserFormOptions; onCreated: () => void }) {
  const [role, setRole] = useState<ManagedRole>("MEMBER");
  const [name, setName] = useState("");
  const [localPart, setLocalPart] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [link, setLink] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<string | null>(null);

  const organizations = options.organizations.filter((o) => o.role === role);
  const isMember = role === "MEMBER";
  const choices = isMember
    ? options.plans.map((p) => ({ value: p.plan_code, label: p.plan_name }))
    : organizations.map((o) => ({ value: o.id, label: o.name }));
  const chosen = choices.some((c) => c.value === link) ? link : (choices[0]?.value ?? "");
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password.length < MIN_PASSWORD) return;
    setSaving(true);
    setError(null);
    setCreated(null);
    try {
      const user = await adminService.createUser({
        email: `${localPart.trim()}@example.test`,
        display_name: name.trim(),
        role,
        password,
        ...(isMember ? { plan_code: chosen } : { organization_id: chosen }),
      });
      setCreated(`${user.display_name} (${user.email}) can sign in now.`);
      setName("");
      setLocalPart("");
      setPassword("");
      onCreated();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card section" aria-labelledby="add-user-heading">
      <h2 id="add-user-heading">Add a user</h2>
      <form onSubmit={(e) => void submit(e)}>
        <div className="field">
          <label htmlFor="user-role">Role</label>
          <select id="user-role" value={role} onChange={(e) => setRole(e.target.value as ManagedRole)}>
            {CREATABLE.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </div>
        <TextField label="Full name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={120} />
        <TextField
          label="Email name"
          hint="Accounts use fictional addresses, so @example.test is added for you."
          value={localPart}
          onChange={(e) => setLocalPart(e.target.value)}
          required
          pattern="[A-Za-z0-9._\-]+"
          autoComplete="off"
        />
        <TextField
          label="Password"
          hint={`At least ${MIN_PASSWORD} characters. Share it with the user yourself; it can't be shown again.`}
          type={showPassword ? "text" : "password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={tooShort ? `Use at least ${MIN_PASSWORD} characters.` : null}
          required
          maxLength={128}
          autoComplete="new-password"
        />
        <label className="field-inline small">
          <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} /> Show password
        </label>
        <div className="field section">
          <label htmlFor="user-link">{isMember ? "Plan" : "Organization"}</label>
          <select id="user-link" value={chosen} onChange={(e) => setLink(e.target.value)} required>
            {choices.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" busy={saving} disabled={!chosen}>
          Add user
        </Button>
      </form>
      {created && (
        <Alert tone="success" title="User added" role="status">
          {created}
        </Alert>
      )}
      {Boolean(error) && <ErrorState error={error} />}
    </section>
  );
}

export function UsersPage() {
  const [filter, setFilter] = useState("");
  const options = useRequest((signal) => adminService.userOptions(signal));
  const users = useRequest((signal, role: string) => adminService.users(role, signal));

  useEffect(() => {
    void options.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once
  }, []);
  useEffect(() => {
    void users.run(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when the filter changes
  }, [filter]);

  return (
    <>
      <PageHeader title="Users" description="Add members, providers and support agents. They can sign in as soon as they're added." />
      {options.state.status === "loading" && <LoadingState />}
      {options.state.status === "error" && <ErrorState error={options.state.error} onRetry={() => void options.run()} />}
      {options.state.status === "success" && (
        <CreateUserForm options={options.state.data} onCreated={() => void users.refresh(filter)} />
      )}

      <section className="section" aria-labelledby="users-heading">
        <h2 id="users-heading">All users</h2>
        <div className="field field-inline">
          <label htmlFor="user-filter">Show</label>
          <select id="user-filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">All roles</option>
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {users.state.status === "loading" && <LoadingState label="Loading users…" />}
        {users.state.status === "error" && <ErrorState error={users.state.error} onRetry={() => void users.run(filter)} />}
        {users.state.status === "success" && users.state.data.length === 0 && <EmptyState title="No users with this role" />}
        {users.state.status === "success" && users.state.data.length > 0 && (
          <div className="table-wrap">
            <table aria-label="Users">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Email</th>
                  <th scope="col">Role</th>
                  <th scope="col">Plan or organization</th>
                  <th scope="col">Last sign-in</th>
                </tr>
              </thead>
              <tbody>
                {users.state.data.map((u) => (
                  <tr key={u.id}>
                    <td>{u.display_name}</td>
                    <td className="mono">{u.email}</td>
                    <td>{ROLE_LABELS[u.role] ?? u.role}</td>
                    <td>
                      {u.plan_name ?? u.organization_name ?? "—"}
                      {u.member_number && <span className="muted small"> · {u.member_number}</span>}
                    </td>
                    <td>{u.last_login_at ? formatDateTime(u.last_login_at) : <span className="muted">Never</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
