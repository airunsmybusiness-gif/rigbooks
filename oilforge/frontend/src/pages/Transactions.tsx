/** Bank import: full-year CSV upload (CIBC & other banks), bulk review &
 * recategorize, transaction splitting, receipt refs, shareholder-ledger
 * posting, and one-click capital-purchase → CCA asset conversion. */
import {
  ArrowRightLeft, CheckSquare, Scissors, Settings, Square, Trash2, Truck,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Select, Table,
  Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const STATUSES = ["business", "shareholder", "exclude"];
const statusTone = (s: string) =>
  s === "business" ? "good" : s === "shareholder" ? "warn" : "neutral";

const CCA_CLASSES = [
  { value: "8", label: "8 — General equipment (20%)" },
  { value: "10", label: "10 — Trucks & trailers (30%)" },
  { value: "12", label: "12 — Small tools <$500 (100%)" },
  { value: "16", label: "16 — Heavy freight truck (40%)" },
  { value: "38", label: "38 — Power-operated movable (30%)" },
  { value: "50", label: "50 — Computers (55%)" },
];

export default function Transactions() {
  const { period } = useStore();
  const [items, setItems] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [shareholders, setShareholders] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [showRules, setShowRules] = useState(false);
  const [posting, setPosting] = useState<any | null>(null);
  const [splitting, setSplitting] = useState<any | null>(null);
  const [toAsset, setToAsset] = useState<any | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkCat, setBulkCat] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get("/api/transactions/categories").then(setCategories);
    api.get("/api/shareholders").then((r) => setShareholders(r.items ?? r));
  }, []);

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
    setSelected(new Set());
  }, [query]);
  useEffect(() => { load(); }, [load]);

  const upload = async (file: File) => {
    setError(""); setMessage("");
    try {
      const r = await api.upload("/api/transactions/import", file);
      setMessage(`Imported ${r.created} transactions` +
        (r.skipped_duplicates ? ` (${r.skipped_duplicates} duplicates skipped)` : "") +
        ". Review the categories below — bulk-select rows to recategorize.");
      load();
    } catch (e: any) { setError(e.message); }
  };

  const patch = async (id: number, body: Record<string, string>) => {
    const updated = await api.put(`/api/transactions/${id}`, body);
    setItems((xs) => xs.map((x) => (x.id === id ? updated : x)));
  };

  const toggle = (id: number) => setSelected((s) => {
    const next = new Set(s);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const allSelected = items.length > 0 && selected.size === items.length;

  const bulkApply = async () => {
    if (!bulkCat || selected.size === 0) return;
    await api.put("/api/transactions/bulk",
      { ids: [...selected], category: bulkCat });
    setMessage(`Recategorized ${selected.size} transactions to ${bulkCat}`);
    setBulkCat("");
    load();
  };

  const unpostedDraws = items.filter(
    (t) => t.status === "shareholder" && !t.posted_shareholder_txn_id).length;

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Bank Import"
        sub="Upload a full year of CIBC (or any bank) CSV — chequing, credit card, or signed-amount formats"
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
      {unpostedDraws > 0 && (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400">
          {unpostedDraws} owner transfer{unpostedDraws > 1 ? "s" : ""} not yet on
          the shareholder ledger — use ⇄ on those rows.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search description…" className="max-w-56" />
        <Select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} className="!w-auto">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="!w-auto">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
      </div>

      {selected.size > 0 && (
        <div className="sticky top-14 z-20 flex flex-wrap items-center gap-2 rounded-xl border border-accent/40 bg-accent-soft px-4 py-2.5">
          <span className="text-sm font-medium text-accent">{selected.size} selected</span>
          <Select value={bulkCat} onChange={(e) => setBulkCat(e.target.value)}
            className="!w-auto !py-1.5">
            <option value="">Set category…</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </Select>
          <Button onClick={bulkApply} disabled={!bulkCat} className="!py-1.5">Apply</Button>
          <Button variant="ghost" onClick={() => setSelected(new Set())} className="!py-1.5">
            Clear
          </Button>
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState>No transactions in this period. Upload your bank CSV —
          headers optional, duplicates skipped automatically.</EmptyState>
      ) : (
        <Table head={<>
          <Th>
            <button onClick={() => setSelected(allSelected ? new Set()
              : new Set(items.map((t) => t.id)))} title="Select all">
              {allSelected ? <CheckSquare size={15} /> : <Square size={15} />}
            </button>
          </Th>
          <Th>Date</Th><Th>Description</Th><Th right>Out</Th><Th right>In</Th>
          <Th>Category</Th><Th>Status</Th><Th right>ITC</Th><Th right>Actions</Th>
        </>}>
          {items.map((t) => (
            <tr key={t.id}
              className={"hover:bg-surface-2 " + (selected.has(t.id) ? "bg-accent-soft/40" : "")}>
              <Td>
                <button onClick={() => toggle(t.id)}>
                  {selected.has(t.id)
                    ? <CheckSquare size={15} className="text-accent" />
                    : <Square size={15} className="text-ink-3" />}
                </button>
              </Td>
              <Td className="whitespace-nowrap">{t.date}</Td>
              <Td className="max-w-[22ch] truncate" >
                {t.description}
                {t.receipt_ref && <span className="ml-1 text-xs text-ink-3">📎{t.receipt_ref}</span>}
              </Td>
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
                <div className="flex justify-end gap-0.5">
                  {t.status === "shareholder" && !t.posted_shareholder_txn_id && (
                    <button className="rounded-lg p-1.5 text-accent hover:bg-accent-soft"
                      title="Post to shareholder ledger" onClick={() => setPosting(t)}>
                      <ArrowRightLeft size={14} />
                    </button>
                  )}
                  {t.posted_shareholder_txn_id && <Badge tone="accent">posted</Badge>}
                  {(t.debit > 0 && !t.split_parent_id && t.status !== "exclude") && (
                    <button className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink-1"
                      title="Split into parts" onClick={() => setSplitting(t)}>
                      <Scissors size={14} />
                    </button>
                  )}
                  {t.debit >= 500 && t.status === "business" && (
                    <button className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink-1"
                      title="Convert to CCA asset" onClick={() => setToAsset(t)}>
                      <Truck size={14} />
                    </button>
                  )}
                  <button className="rounded-lg p-1.5 text-ink-3 hover:bg-bad/10 hover:text-bad"
                    onClick={async () => {
                      if (confirm("Delete this transaction?")) {
                        await api.del(`/api/transactions/${t.id}`); load();
                      }
                    }} title="Delete">
                    <Trash2 size={14} />
                  </button>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      )}

      {posting && (
        <PostModal txn={posting} shareholders={shareholders}
          onClose={() => setPosting(null)}
          onPosted={() => { setPosting(null); load(); }} />
      )}
      {splitting && (
        <SplitModal txn={splitting} categories={categories}
          onClose={() => setSplitting(null)}
          onDone={() => { setSplitting(null); load(); }} />
      )}
      {toAsset && (
        <ToAssetModal txn={toAsset} onClose={() => setToAsset(null)}
          onDone={(msg) => { setToAsset(null); setMessage(msg); load(); }} />
      )}
      {showRules && <RulesModal categories={categories} onClose={() => setShowRules(false)} />}
    </div>
  );
}

function SplitModal({ txn, categories, onClose, onDone }: {
  txn: any; categories: string[]; onClose: () => void; onDone: () => void;
}) {
  const original = txn.debit || txn.credit;
  const [parts, setParts] = useState([
    { amount: original, category: txn.category, note: "" },
    { amount: 0, category: "Owner Withdrawal", note: "" },
  ]);
  const [error, setError] = useState("");
  const total = parts.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const set = (i: number, patch: any) =>
    setParts((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  return (
    <Modal title="Split transaction" onClose={onClose} wide>
      <p className="mb-4 text-sm text-ink-2">
        {txn.date} · {txn.description} · <strong>{money(original)}</strong> —
        parts must total the original; the original is kept (excluded) for the
        audit trail.
      </p>
      <div className="space-y-2">
        {parts.map((p, i) => (
          <div key={i} className="grid grid-cols-[110px_1fr_1fr_32px] items-center gap-2">
            <Input type="number" step="0.01" value={p.amount} aria-label="Amount"
              onChange={(e) => set(i, { amount: Number(e.target.value) })} />
            <Select value={p.category}
              onChange={(e) => set(i, { category: e.target.value })}>
              {categories.map((c) => <option key={c}>{c}</option>)}
            </Select>
            <Input value={p.note} placeholder="note"
              onChange={(e) => set(i, { note: e.target.value })} />
            <button className="text-ink-3 hover:text-bad" title="Remove"
              onClick={() => setParts((ps) => ps.filter((_, j) => j !== i))}>
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Button variant="ghost" onClick={() =>
          setParts((ps) => [...ps, { amount: 0, category: txn.category, note: "" }])}>
          + Add part
        </Button>
        <p className={"text-sm " + (Math.abs(total - original) < 0.01 ? "text-good" : "text-bad")}>
          Parts total {money(total)} / {money(original)}
        </p>
      </div>
      {error && <p className="mt-2 text-sm text-bad">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={Math.abs(total - original) > 0.01} onClick={async () => {
          try {
            await api.post(`/api/transactions/${txn.id}/split`, { parts });
            onDone();
          } catch (e: any) { setError(e.message); }
        }}>Split</Button>
      </div>
    </Modal>
  );
}

function ToAssetModal({ txn, onClose, onDone }: {
  txn: any; onClose: () => void; onDone: (msg: string) => void;
}) {
  const [form, setForm] = useState({ name: txn.description.slice(0, 60), cca_class: "8" });
  const [error, setError] = useState("");
  return (
    <Modal title="Convert to CCA asset" onClose={onClose}>
      <p className="mb-3 text-sm text-ink-2">
        {money(txn.debit)} purchase on {txn.date}. The asset is recorded net of
        GST (full ITC claimed) and starts earning CCA this year.
      </p>
      <div className="space-y-3">
        <Field label="Asset name">
          <Input value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="CCA class">
          <Select value={form.cca_class}
            onChange={(e) => setForm({ ...form, cca_class: e.target.value })}>
            {CCA_CLASSES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </Select>
        </Field>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try {
              const r = await api.post(`/api/transactions/${txn.id}/to-asset`, form);
              onDone(`Asset created (class ${r.cca_class}, cost ${money(r.cost)} net of GST)`);
            } catch (e: any) { setError(e.message); }
          }}>Create asset</Button>
        </div>
      </div>
    </Modal>
  );
}

function PostModal({ txn, shareholders, onClose, onPosted }: {
  txn: any; shareholders: any[]; onClose: () => void; onPosted: () => void;
}) {
  const [shareholderId, setShareholderId] = useState(shareholders[0]?.id ?? 0);
  const [type, setType] = useState(txn.debit > 0 ? "withdrawal" : "contribution");
  const [error, setError] = useState("");
  return (
    <Modal title="Post to shareholder ledger" onClose={onClose}>
      <p className="mb-4 text-sm text-ink-2">
        {txn.date} · {txn.description} · <strong>{money(txn.debit || txn.credit)}</strong>
      </p>
      {shareholders.length === 0 ? (
        <p className="text-sm text-bad">Add a shareholder first (Dividends & Loans page).</p>
      ) : (
        <div className="space-y-3">
          <Field label="Shareholder">
            <Select value={shareholderId} onChange={(e) => setShareholderId(Number(e.target.value))}>
              {shareholders.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
          <Field label="Treat as">
            <Select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="withdrawal">Owner withdrawal (increases loan)</option>
              <option value="personal_expense">Personal expense on corp account</option>
              <option value="contribution">Contribution from shareholder</option>
              <option value="loan_repayment">Loan repayment</option>
            </Select>
          </Field>
          {error && <p className="text-sm text-bad">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={async () => {
              try {
                await api.post("/api/shareholder/post-from-bank", {
                  bank_txn_id: txn.id, shareholder_id: shareholderId, type,
                });
                onPosted();
              } catch (e: any) { setError(e.message); }
            }}>Post entry</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function RulesModal({ categories, onClose }: { categories: string[]; onClose: () => void }) {
  const [rules, setRules] = useState<any[]>([]);
  const [draft, setDraft] = useState({ pattern: "", category: "Other Operating", priority: 100 });
  const load = () => api.get("/api/transactions/classifier-rules").then(setRules);
  useEffect(() => { load(); }, []);
  return (
    <Modal title="Auto-classification rules" onClose={onClose} wide>
      <p className="mb-4 text-sm text-ink-3">
        Regex patterns matched against descriptions, lowest priority first.
      </p>
      <div className="mb-4 grid grid-cols-[1fr_auto_auto_auto] items-end gap-2">
        <Field label="Pattern (regex)">
          <Input value={draft.pattern} placeholder="e.g. UFA|CARDLOCK"
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
