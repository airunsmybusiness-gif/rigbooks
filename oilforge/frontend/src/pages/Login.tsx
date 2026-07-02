/** Sign-in / first-run setup. */
import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Field, Input } from "../components/ui";
import { useStore } from "../store";

export default function Login() {
  const { login } = useStore();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/auth/status").then((s) => setNeedsSetup(s.needs_setup))
      .catch(() => setNeedsSetup(false));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const path = needsSetup ? "/api/auth/register" : "/api/auth/login";
      const r = await api.post(path, { email, password, name });
      login({ name: r.name, email: r.email }, r.token);
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  if (needsSetup === null) return null;
  return (
    <div className="grid min-h-full place-items-center p-4">
      <div className="fade-up w-full max-w-sm">
        <div className="mb-6 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-accent text-3xl text-white">🔥</span>
          <h1 className="mt-3 text-2xl font-bold text-ink-1">OilForge</h1>
          <p className="mt-1 text-sm text-ink-3">
            {needsSetup
              ? "Set up your corporate books — create the local account."
              : "Sign in. Your corporate records stay on this machine."}
          </p>
        </div>
        <form onSubmit={submit}
          className="space-y-3 rounded-2xl border border-line bg-surface-1 p-6 shadow-sm">
          {needsSetup && (
            <Field label="Your name">
              <Input value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. J. Smith" required />
            </Field>
          )}
          <Field label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoFocus />
          </Field>
          <Field label={needsSetup ? "Password (8+ characters)" : "Password"}>
            <Input type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} required
              minLength={needsSetup ? 8 : 1} />
          </Field>
          {error && <p className="text-sm text-bad">{error}</p>}
          <Button type="submit" disabled={busy} className="w-full">
            {needsSetup ? "Create account" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-3">
          Local-first · encrypted backups · CRA 6-year retention
        </p>
      </div>
    </div>
  );
}
