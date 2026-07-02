/** Equipment & CCA: asset registry, maintenance logs, depreciation schedule. */
import { Plus, Trash2, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select,
  Table, Td, Th,
} from "../components/ui";
import { useStore } from "../store";

const CCA_CLASSES = [
  { value: "8", label: "8 — General equipment (20%)" },
  { value: "10", label: "10 — Trucks & trailers (30%)" },
  { value: "10.1", label: "10.1 — Passenger vehicle (30%, capped)" },
  { value: "12", label: "12 — Small tools <$500 (100%)" },
  { value: "16", label: "16 — Heavy freight truck (40%)" },
  { value: "38", label: "38 — Power-operated movable equip. (30%)" },
  { value: "43", label: "43 — M&P machinery (30%)" },
  { value: "50", label: "50 — Computers (55%)" },
];

export default function EquipmentPage() {
  const [tab, setTab] = useState<"assets" | "parts" | "safety">("assets");
  return (
    <div className="fade-up space-y-4">
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface-1 p-1">
        {([["assets", "Assets & CCA"], ["parts", "Parts inventory"],
           ["safety", "Safety & compliance"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={"whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors " +
              (tab === k ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface-2")}>
            {label}
          </button>
        ))}
      </div>
      {tab === "assets" && <AssetsTab />}
      {tab === "parts" && <PartsTab />}
      {tab === "safety" && <SafetyTab />}
    </div>
  );
}

function AssetsTab() {
  const { year } = useStore();
  const [items, setItems] = useState<any[]>([]);
  const [cca, setCca] = useState<any>(null);
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<any | null>(null);

  const load = useCallback(() => {
    api.get("/api/equipment").then((r) => setItems(r.items ?? r));
    api.get(`/api/reports/cca?year=${year}`).then(setCca);
  }, [year]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <PageHeader title="Equipment & CCA"
        sub="Asset registry with maintenance history and the year's depreciation schedule"
        action={<Button onClick={() => setAdding(true)}><Plus size={15} /> Add asset</Button>} />

      {items.length === 0 ? (
        <EmptyState>No equipment yet. Add your units to start CCA tracking.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Asset</Th><Th>Serial</Th><Th>Class</Th><Th right>Cost</Th>
          <Th>Acquired</Th><Th>Status</Th><Th right> </Th>
        </>}>
          {items.map((e) => (
            <tr key={e.id} className="cursor-pointer hover:bg-surface-2"
              onClick={() => setSelected(e)}>
              <Td className="font-medium">{e.name}</Td>
              <Td className="text-xs">{e.serial}</Td>
              <Td><Badge tone="accent">{e.cca_class}</Badge></Td>
              <Td right>{money(e.cost)}</Td>
              <Td>{e.acquired ?? "—"}</Td>
              <Td><Badge tone={e.status === "active" ? "good" : "neutral"}>{e.status}</Badge></Td>
              <Td right><span className="text-xs text-accent">log →</span></Td>
            </tr>
          ))}
        </Table>
      )}

      {cca && cca.classes.length > 0 && (
        <Card title={`CCA schedule — ${year} (first-year additions get the accelerated factor)`}>
          <Table head={<>
            <Th>Class</Th><Th>Description</Th><Th right>Rate</Th>
            <Th right>Opening UCC</Th><Th right>Additions</Th>
            <Th right>Dispositions</Th><Th right>CCA</Th><Th right>Closing UCC</Th>
          </>}>
            {cca.classes.map((r: any) => (
              <tr key={r.class}>
                <Td><Badge tone="accent">{r.class}</Badge></Td>
                <Td className="text-xs">{r.description}</Td>
                <Td right>{(r.rate * 100).toFixed(0)}%</Td>
                <Td right>{money(r.ucc_opening)}</Td>
                <Td right>{money(r.additions)}</Td>
                <Td right>{money(r.dispositions)}</Td>
                <Td right className="font-semibold">{money(r.cca)}</Td>
                <Td right>{money(r.ucc_closing)}</Td>
              </tr>
            ))}
            <tr className="bg-surface-2 font-semibold">
              <Td>Total</Td><Td> </Td><Td right> </Td><Td right> </Td>
              <Td right> </Td><Td right> </Td>
              <Td right>{money(cca.total_cca)}</Td>
              <Td right>{money(cca.total_ucc_closing)}</Td>
            </tr>
          </Table>
          <p className="mt-2 text-xs text-ink-3">
            Claiming CCA is optional each year — your accountant decides how much
            to claim on the T2. This schedule shows the maximum available.
          </p>
        </Card>
      )}

      {adding && (
        <AssetModal onClose={() => setAdding(false)}
          onSaved={() => { setAdding(false); load(); }} />
      )}
      {selected && (
        <MaintenanceModal asset={selected} onClose={() => { setSelected(null); load(); }} />
      )}
    </div>
  );
}

function PartsTab() {
  const [items, setItems] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ name: "", part_number: "",
    qty_on_hand: 0, unit_cost: 0, min_qty: 0, location: "" });
  const load = useCallback(() => {
    api.get("/api/parts").then((r) => setItems(r.items ?? r));
  }, []);
  useEffect(() => { load(); }, [load]);
  const adjust = async (id: number, delta: number) => {
    const reason = delta < 0 ? prompt("Used for (memo):") ?? "" : "";
    await api.post(`/api/parts/${id}/adjust`, { delta, reason });
    load();
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Parts inventory"
        sub="Filters, fluids and consumables — low stock is flagged against minimums" />
      <Card title="Add part">
        <form className="grid grid-cols-2 items-end gap-2 md:grid-cols-6"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/api/parts", form);
            setForm({ ...form, name: "", part_number: "" });
            load();
          }}>
          <Field label="Name"><Input value={form.name} required
            onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Part #"><Input value={form.part_number}
            onChange={(e) => setForm({ ...form, part_number: e.target.value })} /></Field>
          <Field label="Qty"><Input type="number" step="1" value={form.qty_on_hand}
            onChange={(e) => setForm({ ...form, qty_on_hand: Number(e.target.value) })} /></Field>
          <Field label="Unit cost $"><Input type="number" step="0.01" value={form.unit_cost}
            onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} /></Field>
          <Field label="Min qty"><Input type="number" step="1" value={form.min_qty}
            onChange={(e) => setForm({ ...form, min_qty: Number(e.target.value) })} /></Field>
          <Button type="submit"><Plus size={14} /> Add</Button>
        </form>
      </Card>
      {items.length === 0 ? (
        <EmptyState>No parts tracked yet.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Part</Th><Th>Part #</Th><Th right>On hand</Th><Th right>Unit cost</Th>
          <Th>Status</Th><Th right>Stock</Th>
        </>}>
          {items.map((p) => (
            <tr key={p.id} className="hover:bg-surface-2">
              <Td className="font-medium">{p.name}</Td>
              <Td className="text-xs">{p.part_number}</Td>
              <Td right>{p.qty_on_hand}</Td>
              <Td right>{money(p.unit_cost)}</Td>
              <Td>{p.qty_on_hand <= p.min_qty
                ? <Badge tone="warn">low stock</Badge>
                : <Badge tone="good">ok</Badge>}</Td>
              <Td right>
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => adjust(p.id, 1)}>+1</Button>
                  <Button variant="ghost" onClick={() => adjust(p.id, -1)}>use 1</Button>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function SafetyTab() {
  const [items, setItems] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ kind: "certificate", name: "",
    reference: "", issued: "", expires: "" });
  const load = useCallback(() => {
    api.get("/api/safety").then((r) => setItems(r.items ?? r));
  }, []);
  useEffect(() => { load(); }, [load]);
  const daysTo = (d: string | null) => d
    ? Math.ceil((new Date(d).getTime() - Date.now()) / 86400000) : null;
  return (
    <div className="space-y-4">
      <PageHeader title="Safety & compliance"
        sub="Certificates, inspections, permits — expiry dates tracked with warnings" />
      <Card title="Add item">
        <form className="grid grid-cols-2 items-end gap-2 md:grid-cols-6"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/api/safety", {
              ...form, issued: form.issued || null, expires: form.expires || null });
            setForm({ ...form, name: "", reference: "" });
            load();
          }}>
          <Field label="Kind">
            <Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {["certificate", "inspection", "policy", "insurance", "permit"]
                .map((k) => <option key={k}>{k}</option>)}
            </Select>
          </Field>
          <Field label="Name"><Input value={form.name} required placeholder="e.g. H2S Alive"
            onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Reference"><Input value={form.reference}
            onChange={(e) => setForm({ ...form, reference: e.target.value })} /></Field>
          <Field label="Issued"><Input type="date" value={form.issued}
            onChange={(e) => setForm({ ...form, issued: e.target.value })} /></Field>
          <Field label="Expires"><Input type="date" value={form.expires}
            onChange={(e) => setForm({ ...form, expires: e.target.value })} /></Field>
          <Button type="submit"><Plus size={14} /> Add</Button>
        </form>
      </Card>
      {items.length === 0 ? (
        <EmptyState>Nothing tracked yet — add tickets, inspections and policies.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Kind</Th><Th>Name</Th><Th>Reference</Th><Th>Expires</Th><Th>Status</Th>
        </>}>
          {items.map((s) => {
            const d = daysTo(s.expires);
            return (
              <tr key={s.id} className="hover:bg-surface-2">
                <Td><Badge>{s.kind}</Badge></Td>
                <Td className="font-medium">{s.name}</Td>
                <Td className="text-xs">{s.reference}</Td>
                <Td>{s.expires ?? "—"}</Td>
                <Td>{d === null ? <Badge>no expiry</Badge>
                  : d < 0 ? <Badge tone="bad">expired</Badge>
                  : d < 60 ? <Badge tone="warn">{d} days left</Badge>
                  : <Badge tone="good">valid</Badge>}</Td>
              </tr>
            );
          })}
        </Table>
      )}
    </div>
  );
}

function AssetModal({ onClose, onSaved }: any) {
  const [form, setForm] = useState<any>({
    name: "", serial: "", cca_class: "8", cost: 0,
    acquired: new Date().toISOString().slice(0, 10), description: "",
  });
  const [error, setError] = useState("");
  return (
    <Modal title="Add equipment / asset" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Name"><Input value={form.name} required placeholder="e.g. 2022 Skid Steer"
          onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Serial / VIN"><Input value={form.serial}
            onChange={(e) => setForm({ ...form, serial: e.target.value })} /></Field>
          <Field label="CCA class">
            <Select value={form.cca_class}
              onChange={(e) => setForm({ ...form, cca_class: e.target.value })}>
              {CCA_CLASSES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select>
          </Field>
          <Field label="Cost ($, before GST)"><Input type="number" step="100" value={form.cost}
            onChange={(e) => setForm({ ...form, cost: Number(e.target.value) })} /></Field>
          <Field label="Acquired"><Input type="date" value={form.acquired}
            onChange={(e) => setForm({ ...form, acquired: e.target.value })} /></Field>
        </div>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try { await api.post("/api/equipment", form); onSaved(); }
            catch (e: any) { setError(e.message); }
          }}>Save asset</Button>
        </div>
      </div>
    </Modal>
  );
}

function MaintenanceModal({ asset, onClose }: { asset: any; onClose: () => void }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [form, setForm] = useState<any>({
    date: new Date().toISOString().slice(0, 10), kind: "service",
    description: "", cost: 0, vendor: "", hours_reading: "",
  });
  const load = useCallback(() => {
    api.get(`/api/maintenance?equipment_id=${asset.id}&start=1990-01-01&end=2099-12-31`)
      .then((r) => setLogs(r.items));
  }, [asset.id]);
  useEffect(() => { load(); }, [load]);

  return (
    <Modal title={`${asset.name} — maintenance log`} onClose={onClose} wide>
      <form className="mb-4 grid grid-cols-2 items-end gap-2 rounded-xl border border-line bg-surface-2 p-3 md:grid-cols-6"
        onSubmit={async (e) => {
          e.preventDefault();
          await api.post("/api/maintenance", {
            ...form, equipment_id: asset.id,
            hours_reading: form.hours_reading === "" ? null : Number(form.hours_reading),
          });
          setForm({ ...form, description: "", cost: 0 });
          load();
        }}>
        <Field label="Date"><Input type="date" value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
        <Field label="Kind">
          <Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {["service", "repair", "inspection", "fuel", "parts"].map((k) =>
              <option key={k}>{k}</option>)}
          </Select>
        </Field>
        <Field label="Description"><Input value={form.description} required
          onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <Field label="Cost $"><Input type="number" step="0.01" value={form.cost}
          onChange={(e) => setForm({ ...form, cost: Number(e.target.value) })} /></Field>
        <Field label="Hours"><Input type="number" value={form.hours_reading}
          onChange={(e) => setForm({ ...form, hours_reading: e.target.value })} /></Field>
        <Button type="submit"><Wrench size={14} /> Log</Button>
      </form>
      {logs.length === 0 ? (
        <EmptyState>No maintenance recorded for this unit.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Date</Th><Th>Kind</Th><Th>Description</Th><Th right>Hours</Th>
          <Th right>Cost</Th><Th right> </Th>
        </>}>
          {logs.map((l) => (
            <tr key={l.id}>
              <Td>{l.date}</Td>
              <Td><Badge>{l.kind}</Badge></Td>
              <Td>{l.description}</Td>
              <Td right>{l.hours_reading ?? "—"}</Td>
              <Td right>{money(l.cost)}</Td>
              <Td right>
                <button className="rounded-lg p-1.5 text-ink-3 hover:text-bad"
                  onClick={async () => { await api.del(`/api/maintenance/${l.id}`); load(); }}>
                  <Trash2 size={14} />
                </button>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </Modal>
  );
}
