/** Field Entry — mobile-first ticket entry for use on site.
 * Big touch targets, camera photo attachment, and an offline queue:
 * entries created without a connection are stored locally and synced
 * when the network returns. */
import { Camera, CloudOff, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select,
} from "../components/ui";

const QUEUE_KEY = "oilforge_field_queue";

type QueuedEntry = { payload: any; queued_at: string };

function readQueue(): QueuedEntry[] {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); }
  catch { return []; }
}
function writeQueue(q: QueuedEntry[]) {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
}

export default function FieldEntry() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [online, setOnline] = useState(navigator.onLine);
  const [queue, setQueue] = useState<QueuedEntry[]>(readQueue());
  const [recent, setRecent] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const photoRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<any>({
    job_id: "", date: new Date().toISOString().slice(0, 10),
    kind: "day", quantity: 1, rate: 0, description: "", ticket_ref: "",
    equipment_id: "",
  });

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const loadRefs = useCallback(() => {
    api.get("/api/jobs?status=active").then((r) => {
      setJobs(r.items);
      if (r.items.length && !form.job_id) {
        setForm((f: any) => ({ ...f, job_id: String(r.items[0].id),
          rate: r.items[0].day_rate }));
      }
    }).catch(() => {});
    api.get("/api/equipment").then((r) => setEquipment(r.items ?? r)).catch(() => {});
  }, []);
  useEffect(() => { loadRefs(); }, [loadRefs]);

  const loadRecent = useCallback(() => {
    const now = new Date();
    const start = new Date(now.getTime() - 14 * 86400000).toISOString().slice(0, 10);
    api.get(`/api/job-entries?start=${start}&end=${now.toISOString().slice(0, 10)}`)
      .then((r) => setRecent(r.items.slice(0, 8))).catch(() => {});
  }, []);
  useEffect(() => { loadRecent(); }, [loadRecent]);

  const jobById = (id: string) => jobs.find((j) => String(j.id) === id);

  const submitOne = async (payload: any, file: File | null) => {
    const created = await api.post("/api/job-entries", payload);
    if (file) await api.upload(`/api/attachments/job_entries/${created.id}`, file);
    return created;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...form, job_id: Number(form.job_id),
      equipment_id: form.equipment_id ? Number(form.equipment_id) : null,
    };
    try {
      await submitOne(payload, photo);
      setMessage(`Ticket saved — ${money(payload.quantity * payload.rate)}`);
      setPhoto(null);
      setForm({ ...form, description: "", ticket_ref: "" });
      loadRecent();
    } catch {
      // Offline or server unreachable → queue it (photo can't be queued).
      const q = [...queue, { payload, queued_at: new Date().toISOString() }];
      setQueue(q);
      writeQueue(q);
      setMessage(photo
        ? "No connection — entry queued locally (re-attach the photo after sync)."
        : "No connection — entry queued locally and will sync automatically.");
      setPhoto(null);
      setForm({ ...form, description: "", ticket_ref: "" });
    }
  };

  const sync = useCallback(async () => {
    const q = readQueue();
    if (!q.length) return;
    const remaining: QueuedEntry[] = [];
    let synced = 0;
    for (const item of q) {
      try { await submitOne(item.payload, null); synced++; }
      catch { remaining.push(item); }
    }
    setQueue(remaining);
    writeQueue(remaining);
    if (synced) {
      setMessage(`Synced ${synced} queued entr${synced > 1 ? "ies" : "y"} ✓`);
      loadRecent();
    }
  }, [loadRecent]);

  // Auto-sync when connectivity returns or the page opens.
  useEffect(() => { if (online) sync(); }, [online, sync]);

  const selected = jobById(form.job_id);

  return (
    <div className="fade-up mx-auto max-w-xl space-y-4">
      <PageHeader title="Field entry"
        sub="Quick tickets from site — works offline, syncs when you're back in range"
        action={online
          ? <Badge tone="good">online</Badge>
          : <Badge tone="warn"><CloudOff size={11} />&nbsp;offline</Badge>} />

      {queue.length > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700 dark:text-amber-400">
          <span>{queue.length} entr{queue.length > 1 ? "ies" : "y"} waiting to sync</span>
          <Button variant="ghost" onClick={sync}><RefreshCw size={14} /> Sync now</Button>
        </div>
      )}
      {message && <p className="rounded-xl bg-good/10 px-4 py-2 text-sm text-good">{message}</p>}

      {jobs.length === 0 ? (
        <EmptyState>No active jobs. Create one on the Jobs page first.</EmptyState>
      ) : (
        <Card>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Job">
              <Select value={form.job_id} className="!py-3 text-base"
                onChange={(e) => {
                  const j = jobById(e.target.value);
                  setForm({ ...form, job_id: e.target.value,
                    rate: j ? (form.kind === "hours" ? j.hourly_rate : j.day_rate) : form.rate });
                }}>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.number} — {j.title || j.client_name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date">
                <Input type="date" value={form.date} className="!py-3 text-base"
                  onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </Field>
              <Field label="Kind">
                <Select value={form.kind} className="!py-3 text-base"
                  onChange={(e) => {
                    const kind = e.target.value;
                    const j = selected;
                    setForm({ ...form, kind,
                      rate: j ? (kind === "hours" ? j.hourly_rate
                        : kind === "mobilization" ? j.mobilization_fee : j.day_rate)
                        : form.rate });
                  }}>
                  <option value="day">Day rate</option>
                  <option value="hours">Hours</option>
                  <option value="mobilization">Mobilization</option>
                  <option value="charge">Other charge</option>
                </Select>
              </Field>
              <Field label={form.kind === "hours" ? "Hours" : "Quantity"}>
                <Input type="number" step="0.5" value={form.quantity}
                  className="!py-3 text-base"
                  onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
              </Field>
              <Field label="Rate ($)">
                <Input type="number" step="0.01" value={form.rate}
                  className="!py-3 text-base"
                  onChange={(e) => setForm({ ...form, rate: Number(e.target.value) })} />
              </Field>
            </div>
            <Field label="Description / work performed">
              <Input value={form.description} placeholder="e.g. Completions support, tower 2"
                className="!py-3 text-base"
                onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Field ticket #">
                <Input value={form.ticket_ref} placeholder="FT-101"
                  className="!py-3 text-base"
                  onChange={(e) => setForm({ ...form, ticket_ref: e.target.value })} />
              </Field>
              <Field label="Equipment used">
                <Select value={form.equipment_id} className="!py-3 text-base"
                  onChange={(e) => setForm({ ...form, equipment_id: e.target.value })}>
                  <option value="">—</option>
                  {equipment.map((eq) => <option key={eq.id} value={eq.id}>{eq.name}</option>)}
                </Select>
              </Field>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={() => photoRef.current?.click()}
                className="!py-3">
                <Camera size={17} /> {photo ? "1 photo attached" : "Attach ticket photo"}
              </Button>
              {photo && (
                <button type="button" className="text-ink-3 hover:text-bad"
                  onClick={() => setPhoto(null)} title="Remove photo">
                  <Trash2 size={16} />
                </button>
              )}
              <input ref={photoRef} type="file" accept="image/*" capture="environment"
                hidden onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
            </div>

            <Button type="submit" className="w-full !py-3.5 text-base">
              <Plus size={18} /> Save ticket — {money(form.quantity * form.rate)}
            </Button>
          </form>
        </Card>
      )}

      {recent.length > 0 && (
        <Card title="Recent tickets (14 days)">
          <ul className="divide-y divide-line text-sm">
            {recent.map((r) => (
              <li key={r.id} className="flex items-center justify-between py-2">
                <span className="text-ink-2">
                  {r.date} · {r.description || r.kind}
                  {r.ticket_ref && <span className="text-ink-3"> · {r.ticket_ref}</span>}
                </span>
                <span className="font-medium tabular-nums">
                  {money(r.quantity * r.rate)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
