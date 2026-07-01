/** Bank statement import: CSV upload with auto-classification, inline
 * category/status editing (recalculates ITC server-side), filters,
 * and management of the classifier rules. */
import { Settings, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select,
  Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const STATUSES = ["business", "personal", "exclude"];
const statusTone = (s: string) =>
  s === "business" ? "good" : s === "personal" ? "warn" : "neutral";

export default function Transactions() {
  const { period } = useStore();
  const [items, setItems] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showRules, setShowRules] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.get("/api/transactions/categories").then(setCategories); }, []);

  const query = useMemo(() => {
    const p = new URLSearchParams({ start: period.start, end: period.end });
    if (q) p.set("q", q);
    if (catFilter) p.set("category", catFilter);
    if (statusFilter) p.set("status", statusFilter);
    return p.toString();
  }, [period, q, catFilter, statusFilter]);

  const load = useCallback(() => {
    api.get(`/api/transactions?${query}`).then((r) => setItems(r.items))
      .catch((e) => setError(e.message));
  }, [query]);
  useEffect(() => { load(); }, [load]);

  const upload = async (file: File) => {
    setError(""); setMessage("");
    try {
      const r = await api.upload("/api/transactions/import", file);
      setMessage(`Imported ${r.created} transactions` +
        (r.skipped_duplicates ? ` (${r.skipped_duplicates} duplicates skipped)` : ""));
      load();
    } catch (e: any) { setError(e.message); }
  };

  const patch = async (id: number, body: Record<string, string>) => {
    const updated = await api.put(`/api/transactions/${id}`, body);
    setItems((xs) => xs.map((x) => (x.id === id ? updated : x)));
  };

  const totals = useMemo(() => ({
    revenue: items.filter((t) => t.category === "Revenue - Oilfield Services")
      .reduce((s, t) => s + t.credit, 0),
    expenses: items.filter((t) => t.status === "business").reduce((s, t) => s + t.debit, 0),
    itc: items.reduce((s, t) => s + t.itc, 0),
  }), [items]);

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Bank Import" sub="Upload statements — every line is auto-categorized with CRA ITCs"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowRules(true)}>
              <Settings size={15} /> Classifier rules
            </Button>
            <Button onClick={() => fileRef.current?.click()}>
              <Upload size={15} /> Upload CSV
            </Button>
            <input ref={fileRef} type="file" accept=".csv" hidden
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </div>
        } />

      {message && <p className="rounded-xl bg-good/10 px-4 py-2 text-sm text-good">{message}</p>}
      {error && <p className="rounded-xl bg-bad/10 px-4 py-2 text-sm text-bad">{error}</p>}

      <div className="grid grid-cols-3 gap-4">
        {[["Bank revenue", totals.revenue], ["Business expenses", totals.expenses],
          ["ITCs", totals.itc]].map(([label, v]) => (
          <div key={label as string} className="rounded-2xl border border-line bg-surface-1 p-4">
            <p className="text-xs uppercase tracking-wide text-ink-3">{label}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{money(v as number)}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search description…" className="max-w-60" />
        <Select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} className="!w-auto">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="!w-auto">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
      </div>

      {items.length === 0 ? (
        <EmptyState>
          No transactions in this period. Upload a bank CSV
          (columns: Date, Description, Debit, Credit) to get started.
        </EmptyState>
      ) : (
        <Table head={<>
          <Th>Date</Th><Th>Description</Th><Th right>Debit</Th><Th right>Credit</Th>
          <Th>Category</Th><Th>Status</Th><Th right>ITC</Th><Th right> </Th>
        </>}>
          {items.map((t) => (
            <tr key={t.id} className="hover:bg-surface-2">
              <Td className="whitespace-nowrap">{t.date}</Td>
              <Td className="max-w-[26ch] truncate" >{t.description}</Td>
              <Td right>{t.debit ? money(t.debit) : ""}</Td>
              <Td right>{t.credit ? money(t.credit) : ""}</Td>
              <Td>
                <Select value={t.category} className="!py-1 text-xs"
                  onChange={(e) => patch(t.id, { category: e.target.value })}>
                  {categories.map((c) => <option key={c}>{c}</option>)}
                </Select>
              </Td>
              <Td>
                <button onClick={() => patch(t.id, {
                  status: STATUSES[(STATUSES.indexOf(t.status) + 1) % STATUSES.length],
                })} title="Click to cycle status">
                  <Badge tone={statusTone(t.status) as any}>{t.status}</Badge>
                </button>
              </Td>
              <Td right>{t.itc ? money(t.itc) : "—"}</Td>
              <Td right>
                <button className="rounded-lg p-1.5 text-ink-3 hover:bg-bad/10 hover:text-bad"
                  onClick={async () => {
                    if (confirm("Delete this transaction?")) {
                      await api.del(`/api/transactions/${t.id}`); load();
                    }
                  }} title="Delete">
                  <Trash2 size={14} />
                </button>
              </Td>
            </tr>
          ))}
        </Table>
      )}

      {showRules && <RulesModal categories={categories} onClose={() => setShowRules(false)} />}
    </div>
  );
}

function RulesModal({ categories, onClose }: { categories: string[]; onClose: () => void }) {
  const [rules, setRules] = useState<any[]>([]);
  const [draft, setDraft] = useState({ pattern: "", category: "Other Business", priority: 100 });
  const load = () => api.get("/api/transactions/classifier-rules").then(setRules);
  useEffect(() => { load(); }, []);

  return (
    <Modal title="Auto-classification rules" onClose={onClose} wide>
      <p className="mb-4 text-sm text-ink-3">
        Rules are regex patterns matched against the transaction description
        (top to bottom by priority). Imports use them automatically.
      </p>
      <div className="mb-4 grid grid-cols-[1fr_auto_auto_auto] items-end gap-2">
        <Field label="Pattern (regex)">
          <Input value={draft.pattern} placeholder="e.g. FLYING J|PILOT"
            onChange={(e) => setDraft({ ...draft, pattern: e.target.value })} />
        </Field>
        <Field label="Category">
          <Select value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </Select>
        </Field>
        <Field label="Priority">
          <Input type="number" value={draft.priority} className="w-20"
            onChange={(e) => setDraft({ ...draft, priority: Number(e.target.value) })} />
        </Field>
        <Button onClick={async () => {
          if (!draft.pattern) return;
          await api.post("/api/transactions/classifier-rules", draft);
          setDraft({ ...draft, pattern: "" });
          load();
        }}>Add</Button>
      </div>
      <Table head={<><Th>Priority</Th><Th>Pattern</Th><Th>Category</Th><Th right> </Th></>}>
        {rules.map((r) => (
          <tr key={r.id}>
            <Td>{r.priority}</Td>
            <Td className="font-mono text-xs">{r.pattern}</Td>
            <Td>{r.category}</Td>
            <Td right>
              <button className="rounded-lg p-1.5 text-ink-3 hover:text-bad"
                onClick={async () => {
                  await api.del(`/api/transactions/classifier-rules/${r.id}`); load();
                }}><Trash2 size={14} /></button>
            </Td>
          </tr>
        ))}
      </Table>
    </Modal>
  );
}
