/** Bank import: CSV upload with oilfield classifier, inline edits, and
 * one-click posting of owner draws to the shareholder ledger. */
import { ArrowRightLeft, Settings, Trash2, Upload } from "lucide-react";
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

  const unpostedDraws = items.filter(
    (t) => t.status === "shareholder" && !t.posted_shareholder_txn_id).length;

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Bank Import"
        sub="Upload statements — owner transfers flag for the shareholder ledger automatically"
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
          {unpostedDraws} owner transfer{unpostedDraws > 1 ? "s" : ""} not yet posted
          to the shareholder ledger — use the ⇄ button on those rows.
        </p>
      )}

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
        <EmptyState>No transactions in this period. Upload a bank CSV
          (Date, Description, Debit, Credit).</EmptyState>
      ) : (
        <Table head={<>
          <Th>Date</Th><Th>Description</Th><Th right>Debit</Th><Th right>Credit</Th>
          <Th>Category</Th><Th>Status</Th><Th right>ITC</Th><Th right> </Th>
        </>}>
          {items.map((t) => (
            <tr key={t.id} className="hover:bg-surface-2">
              <Td className="whitespace-nowrap">{t.date}</Td>
              <Td className="max-w-[24ch] truncate">{t.description}</Td>
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
                      title="Post to shareholder ledger"
                      onClick={() => setPosting(t)}>
                      <ArrowRightLeft size={14} />
                    </button>
                  )}
                  {t.posted_shareholder_txn_id && (
                    <Badge tone="accent">posted</Badge>
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
      {showRules && <RulesModal categories={categories} onClose={() => setShowRules(false)} />}
    </div>
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
