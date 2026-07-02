/** Jobs & field tickets: clients, well sites, work orders, day/hour entries,
 * live profitability, and one-click progress invoicing. */
import { FileText, Hammer, Plus, Trash2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select,
  Table, Td, Th,
} from "../components/ui";

const STATUS_TONE: Record<string, any> = {
  quoted: "neutral", active: "good", complete: "accent", closed: "neutral",
};

export default function Jobs() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [sites, setSites] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [creating, setCreating] = useState(false);
  const [newClient, setNewClient] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get("/api/jobs").then((r) => setJobs(r.items)).catch((e) => setError(e.message));
    api.get("/api/clients").then((r) => setClients(r.items ?? r));
    api.get("/api/sites").then((r) => setSites(r.items ?? r));
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Jobs & field tickets"
        sub="Contracts, day rates, mobilization and holdbacks — billed straight from field entries"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setNewClient(true)}>
              <UserPlus size={15} /> New client
            </Button>
            <Button onClick={() => setCreating(true)} disabled={clients.length === 0}
              title={clients.length === 0 ? "Add a client first" : undefined}>
              <Plus size={15} /> New job
            </Button>
          </div>
        } />
      {error && <p className="rounded-xl bg-bad/10 px-4 py-2 text-sm text-bad">{error}</p>}

      {jobs.length === 0 ? (
        <EmptyState>
          <Hammer className="mx-auto mb-2" size={22} />
          No jobs yet. Add a client, then create your first work order.
        </EmptyState>
      ) : (
        <Table head={<>
          <Th>Job #</Th><Th>Title</Th><Th>Client</Th><Th>Site</Th><Th>Rate</Th>
          <Th>Status</Th><Th right> </Th>
        </>}>
          {jobs.map((j) => (
            <tr key={j.id} className="cursor-pointer hover:bg-surface-2"
              onClick={() => setSelected(j)}>
              <Td className="font-medium">{j.number}</Td>
              <Td>{j.title}</Td>
              <Td>{j.client_name}</Td>
              <Td className="text-xs">{j.site_name}{j.site_lsd ? ` (${j.site_lsd})` : ""}</Td>
              <Td className="text-xs">
                {j.rate_type === "day_rate" ? `${money(j.day_rate)}/day`
                  : j.rate_type === "hourly" ? `${money(j.hourly_rate)}/hr`
                  : money(j.fixed_price)}
                {j.holdback_pct > 0 && <span className="text-ink-3"> · {j.holdback_pct}% HB</span>}
              </Td>
              <Td><Badge tone={STATUS_TONE[j.status]}>{j.status}</Badge></Td>
              <Td right><span className="text-xs text-accent">open →</span></Td>
            </tr>
          ))}
        </Table>
      )}

      {creating && (
        <JobModal clients={clients} sites={sites} onClose={() => setCreating(false)}
          onSaved={() => { setCreating(false); load(); }} />
      )}
      {newClient && (
        <ClientModal onClose={() => setNewClient(false)}
          onSaved={() => { setNewClient(false); load(); }} />
      )}
      {selected && (
        <JobDetail job={selected} onClose={() => { setSelected(null); load(); }} />
      )}
    </div>
  );
}

function JobModal({ clients, sites, onClose, onSaved }: any) {
  const [form, setForm] = useState<any>({
    client_id: clients[0]?.id ?? 0, site_id: "", title: "",
    rate_type: "day_rate", day_rate: 0, hourly_rate: 0, fixed_price: 0,
    mobilization_fee: 0, holdback_pct: 0, status: "active",
    start_date: new Date().toISOString().slice(0, 10),
  });
  const [error, setError] = useState("");
  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));
  return (
    <Modal title="New job / work order" onClose={onClose} wide>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <Field label="Client">
          <Select value={form.client_id} onChange={(e) => set("client_id", Number(e.target.value))}>
            {clients.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Well site (optional)">
          <Select value={form.site_id} onChange={(e) => set("site_id", e.target.value)}>
            <option value="">—</option>
            {sites.map((s: any) => <option key={s.id} value={s.id}>{s.name} {s.lsd}</option>)}
          </Select>
        </Field>
        <Field label="Title">
          <Input value={form.title} placeholder="e.g. Completions support"
            onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label="Rate type">
          <Select value={form.rate_type} onChange={(e) => set("rate_type", e.target.value)}>
            <option value="day_rate">Day rate</option>
            <option value="hourly">Hourly</option>
            <option value="fixed">Fixed price</option>
          </Select>
        </Field>
        {form.rate_type === "day_rate" && (
          <Field label="Day rate ($)">
            <Input type="number" step="50" value={form.day_rate}
              onChange={(e) => set("day_rate", Number(e.target.value))} />
          </Field>
        )}
        {form.rate_type === "hourly" && (
          <Field label="Hourly rate ($)">
            <Input type="number" step="5" value={form.hourly_rate}
              onChange={(e) => set("hourly_rate", Number(e.target.value))} />
          </Field>
        )}
        {form.rate_type === "fixed" && (
          <Field label="Fixed price ($)">
            <Input type="number" step="100" value={form.fixed_price}
              onChange={(e) => set("fixed_price", Number(e.target.value))} />
          </Field>
        )}
        <Field label="Mobilization fee ($)">
          <Input type="number" step="50" value={form.mobilization_fee}
            onChange={(e) => set("mobilization_fee", Number(e.target.value))} />
        </Field>
        <Field label="Holdback %">
          <Input type="number" min={0} max={20} value={form.holdback_pct}
            onChange={(e) => set("holdback_pct", Number(e.target.value))} />
        </Field>
        <Field label="Start date">
          <Input type="date" value={form.start_date}
            onChange={(e) => set("start_date", e.target.value)} />
        </Field>
      </div>
      {error && <p className="mt-2 text-sm text-bad">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button onClick={async () => {
          try {
            await api.post("/api/jobs", { ...form, site_id: form.site_id || null });
            onSaved();
          } catch (e: any) { setError(e.message); }
        }}>Create job</Button>
      </div>
    </Modal>
  );
}

function ClientModal({ onClose, onSaved }: any) {
  const [form, setForm] = useState({ name: "", contact: "", email: "", phone: "",
    address: "", gst_number: "" });
  const [site, setSite] = useState({ name: "", lsd: "", region: "" });
  const [error, setError] = useState("");
  return (
    <Modal title="New client" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Company name"><Input value={form.name} required
          onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Contact"><Input value={form.contact}
            onChange={(e) => setForm({ ...form, contact: e.target.value })} /></Field>
          <Field label="Phone"><Input value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        </div>
        <Field label="Billing address"><Input value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
        <p className="pt-1 text-xs font-medium text-ink-2">First well site (optional)</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Site name"><Input value={site.name} placeholder="e.g. Well 7-11"
            onChange={(e) => setSite({ ...site, name: e.target.value })} /></Field>
          <Field label="LSD"><Input value={site.lsd} placeholder="07-11-048-09W5"
            onChange={(e) => setSite({ ...site, lsd: e.target.value })} /></Field>
        </div>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try {
              const c = await api.post("/api/clients", form);
              if (site.name) await api.post("/api/sites", { ...site, client_id: c.id });
              onSaved();
            } catch (e: any) { setError(e.message); }
          }}>Save client</Button>
        </div>
      </div>
    </Modal>
  );
}

function JobDetail({ job, onClose }: { job: any; onClose: () => void }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [prof, setProf] = useState<any>(null);
  const [equipment, setEquipment] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [entry, setEntry] = useState<any>({
    date: new Date().toISOString().slice(0, 10), kind: "day",
    description: "", quantity: 1,
    rate: job.rate_type === "hourly" ? job.hourly_rate : job.day_rate,
    ticket_ref: "", equipment_id: "",
  });

  const load = useCallback(() => {
    api.get(`/api/job-entries?job_id=${job.id}&start=1990-01-01&end=2099-12-31`)
      .then((r) => setEntries(r.items));
    api.get(`/api/jobs/${job.id}/profitability`).then(setProf);
    api.get("/api/equipment").then((r) => setEquipment(r.items ?? r));
  }, [job.id]);
  useEffect(() => { load(); }, [load]);

  const addEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/api/job-entries", {
      ...entry, job_id: job.id,
      equipment_id: entry.equipment_id || null,
    });
    setEntry({ ...entry, description: "", ticket_ref: "" });
    load();
  };

  return (
    <Modal title={`${job.number} — ${job.title || job.client_name}`} onClose={onClose} wide>
      {prof && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["Earned", prof.earned], ["Costs", prof.costs],
            ["Margin", prof.margin], ["Unbilled", prof.unbilled]].map(([label, v]) => (
            <div key={label as string} className="rounded-xl border border-line bg-surface-2 p-3">
              <p className="text-[11px] uppercase tracking-wide text-ink-3">{label}</p>
              <p className="text-base font-semibold tabular-nums">{money(v as number)}</p>
            </div>
          ))}
        </div>
      )}
      {prof?.holdback_outstanding > 0 && (
        <p className="mb-3 text-xs text-ink-3">
          Holdback outstanding: {money(prof.holdback_outstanding)} ·
          margin {prof.margin_pct}%
        </p>
      )}

      <form onSubmit={addEntry}
        className="mb-4 grid grid-cols-2 items-end gap-2 rounded-xl border border-line bg-surface-2 p-3 md:grid-cols-7">
        <Field label="Date"><Input type="date" value={entry.date}
          onChange={(e) => setEntry({ ...entry, date: e.target.value })} /></Field>
        <Field label="Kind">
          <Select value={entry.kind} onChange={(e) => {
            const kind = e.target.value;
            setEntry({ ...entry, kind,
              rate: kind === "mobilization" ? job.mobilization_fee
                : kind === "hours" ? job.hourly_rate : job.day_rate });
          }}>
            <option value="day">Day</option>
            <option value="hours">Hours</option>
            <option value="mobilization">Mob</option>
            <option value="charge">Charge</option>
          </Select>
        </Field>
        <Field label="Qty"><Input type="number" step="0.5" value={entry.quantity}
          onChange={(e) => setEntry({ ...entry, quantity: Number(e.target.value) })} /></Field>
        <Field label="Rate $"><Input type="number" step="0.01" value={entry.rate}
          onChange={(e) => setEntry({ ...entry, rate: Number(e.target.value) })} /></Field>
        <Field label="Ticket #"><Input value={entry.ticket_ref} placeholder="FT-101"
          onChange={(e) => setEntry({ ...entry, ticket_ref: e.target.value })} /></Field>
        <Field label="Equipment">
          <Select value={entry.equipment_id}
            onChange={(e) => setEntry({ ...entry, equipment_id: e.target.value })}>
            <option value="">—</option>
            {equipment.map((eq) => <option key={eq.id} value={eq.id}>{eq.name}</option>)}
          </Select>
        </Field>
        <Button type="submit"><Plus size={14} /> Add</Button>
      </form>

      {message && <p className="mb-2 rounded-xl bg-good/10 px-3 py-2 text-sm text-good">{message}</p>}

      <Table head={<>
        <Th>Date</Th><Th>Kind</Th><Th>Ticket</Th><Th right>Qty</Th><Th right>Rate</Th>
        <Th right>Amount</Th><Th>Billed</Th><Th right> </Th>
      </>}>
        {entries.map((en) => (
          <tr key={en.id}>
            <Td>{en.date}</Td>
            <Td>{en.kind}</Td>
            <Td className="text-xs">{en.ticket_ref}</Td>
            <Td right>{en.quantity}</Td>
            <Td right>{money(en.rate)}</Td>
            <Td right>{money(en.quantity * en.rate)}</Td>
            <Td>{en.invoice_id
              ? <Badge tone="good">billed</Badge>
              : <Badge tone="neutral">unbilled</Badge>}</Td>
            <Td right>
              {!en.invoice_id && (
                <button className="rounded-lg p-1.5 text-ink-3 hover:text-bad" title="Delete"
                  onClick={async () => { await api.del(`/api/job-entries/${en.id}`); load(); }}>
                  <Trash2 size={14} />
                </button>
              )}
            </Td>
          </tr>
        ))}
      </Table>

      <div className="mt-4 flex justify-end">
        <Button onClick={async () => {
          try {
            const inv = await api.post(`/api/invoices/from-job/${job.id}`);
            setMessage(`Invoice ${inv.number} created for ${money(inv.amount_due_now)} (holdback ${money(inv.holdback)})`);
            load();
          } catch (e: any) { setMessage(e.message); }
        }}>
          <FileText size={15} /> Invoice unbilled entries
        </Button>
      </div>
    </Modal>
  );
}
