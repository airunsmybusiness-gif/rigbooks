/** Customer invoicing: line-item builder, status workflow (draft → sent →
 * paid books revenue automatically), PDF download, customer management. */
import { Download, Plus, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select,
  Table, Td, Th,
} from "../components/ui";

const STATUS_TONE: Record<string, "neutral" | "accent" | "good" | "bad"> = {
  draft: "neutral", sent: "accent", paid: "good", void: "bad",
};

type Line = { description: string; quantity: number; unit_price: number };

export default function Invoices() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [newCustomer, setNewCustomer] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    api.get("/api/invoices").then(setInvoices).catch((e) => setError(e.message));
    api.get("/api/customers").then((r) => setCustomers(r.items ?? r));
  };
  useEffect(load, []);

  const setStatus = async (inv: any, status: string) => {
    await api.put(`/api/invoices/${inv.id}`, { status });
    load();
  };

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Invoices" sub="Bill customers, download PDFs — paid invoices book revenue automatically"
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setNewCustomer(true)}>
              <UserPlus size={15} /> New customer
            </Button>
            <Button onClick={() => setCreating(true)} disabled={customers.length === 0}
              title={customers.length === 0 ? "Add a customer first" : undefined}>
              <Plus size={15} /> New invoice
            </Button>
          </div>
        } />
      {error && <p className="rounded-xl bg-bad/10 px-4 py-2 text-sm text-bad">{error}</p>}

      {invoices.length === 0 ? (
        <EmptyState>
          No invoices yet. {customers.length === 0 ? "Add a customer, then create your first invoice." : "Create your first invoice."}
        </EmptyState>
      ) : (
        <Table head={<>
          <Th>Number</Th><Th>Customer</Th><Th>Date</Th><Th>Status</Th>
          <Th right>Subtotal</Th><Th right>GST</Th><Th right>Total</Th><Th right> </Th>
        </>}>
          {invoices.map((inv) => (
            <tr key={inv.id} className="hover:bg-surface-2">
              <Td className="font-medium">{inv.number}</Td>
              <Td>{inv.customer_name}</Td>
              <Td>{inv.date}</Td>
              <Td>
                <Select value={inv.status} className="!w-auto !py-1 text-xs"
                  onChange={(e) => setStatus(inv, e.target.value)}>
                  {["draft", "sent", "paid", "void"].map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Td>
              <Td right>{money(inv.subtotal)}</Td>
              <Td right>{money(inv.gst)}</Td>
              <Td right className="font-semibold">{money(inv.total)}</Td>
              <Td right>
                <div className="flex justify-end gap-0.5">
                  <button className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink-1"
                    title="Download PDF"
                    onClick={() => api.download(`/api/invoices/${inv.id}/pdf`, `${inv.number}.pdf`)}>
                    <Download size={14} />
                  </button>
                  <button className="rounded-lg p-1.5 text-ink-3 hover:bg-bad/10 hover:text-bad"
                    title="Delete"
                    onClick={async () => {
                      if (confirm(`Delete invoice ${inv.number}?`)) {
                        await api.del(`/api/invoices/${inv.id}`); load();
                      }
                    }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      )}

      {creating && (
        <InvoiceModal customers={customers} onClose={() => setCreating(false)}
          onSaved={() => { setCreating(false); load(); }} />
      )}
      {newCustomer && (
        <CustomerModal onClose={() => setNewCustomer(false)}
          onSaved={() => { setNewCustomer(false); load(); }} />
      )}
    </div>
  );
}

function InvoiceModal({ customers, onClose, onSaved }: {
  customers: any[]; onClose: () => void; onSaved: () => void;
}) {
  const [customerId, setCustomerId] = useState(customers[0]?.id ?? 0);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([
    { description: "", quantity: 1, unit_price: 0 },
  ]);
  const [error, setError] = useState("");

  const subtotal = lines.reduce((s, l) => s + l.quantity * l.unit_price, 0);

  const save = async () => {
    try {
      await api.post("/api/invoices", {
        customer_id: Number(customerId), date, due_date: dueDate || null, notes,
        lines: lines.filter((l) => l.description),
      });
      onSaved();
    } catch (e: any) { setError(e.message); }
  };

  const setLine = (i: number, patch: Partial<Line>) =>
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  return (
    <Modal title="New invoice" onClose={onClose} wide>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Customer">
          <Select value={customerId} onChange={(e) => setCustomerId(Number(e.target.value))}>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Invoice date">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label="Due date">
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
      </div>
      <div className="mt-4 space-y-2">
        <p className="text-xs font-medium text-ink-2">Line items</p>
        {lines.map((l, i) => (
          <div key={i} className="grid grid-cols-[1fr_80px_110px_32px] items-center gap-2">
            <Input placeholder="Description — e.g. Hotshot delivery, wait time"
              value={l.description}
              onChange={(e) => setLine(i, { description: e.target.value })} />
            <Input type="number" step="0.5" value={l.quantity} aria-label="Quantity"
              onChange={(e) => setLine(i, { quantity: Number(e.target.value) })} />
            <Input type="number" step="0.01" value={l.unit_price} aria-label="Unit price"
              onChange={(e) => setLine(i, { unit_price: Number(e.target.value) })} />
            <button className="text-ink-3 hover:text-bad" title="Remove line"
              onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        <Button variant="ghost" onClick={() =>
          setLines((ls) => [...ls, { description: "", quantity: 1, unit_price: 0 }])}>
          <Plus size={14} /> Add line
        </Button>
      </div>
      <Field label="Notes" className="mt-3">
        <Input value={notes} onChange={(e) => setNotes(e.target.value)}
          placeholder="shown on the PDF" />
      </Field>
      <div className="mt-4 flex items-center justify-between">
        <p className="text-sm text-ink-2">
          Subtotal <strong className="text-ink-1">{money(subtotal)}</strong> + GST
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save}>Create invoice</Button>
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-bad">{error}</p>}
    </Modal>
  );
}

function CustomerModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: "", email: "", phone: "", address: "", gst_number: "", is_ccpc: false,
  });
  const [error, setError] = useState("");
  return (
    <Modal title="New customer" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Name"><Input value={form.name} required
          onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Email"><Input value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Phone"><Input value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        </div>
        <Field label="Address"><Input value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
        <Field label="GST number"><Input value={form.gst_number}
          onChange={(e) => setForm({ ...form, gst_number: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm text-ink-1">
          <input type="checkbox" checked={form.is_ccpc}
            onChange={(e) => setForm({ ...form, is_ccpc: e.target.checked })}
            className="size-4 accent-(--accent)" />
          Incorporated (CCPC) — relevant for T4A box 048
        </label>
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={async () => {
            try { await api.post("/api/customers", form); onSaved(); }
            catch (e: any) { setError(e.message); }
          }}>Save customer</Button>
        </div>
      </div>
    </Modal>
  );
}
