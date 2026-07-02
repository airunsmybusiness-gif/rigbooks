/** Invoices with holdback visibility and release, PDF download. */
import { Download, Lock, LockOpen, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, money } from "../api";
import {
  Badge, EmptyState, PageHeader, Select, Table, Td, Th,
} from "../components/ui";

const STATUS_TONE: Record<string, any> = {
  draft: "neutral", sent: "accent", paid: "good", void: "bad",
};

export default function Invoices() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [error, setError] = useState("");

  const load = () =>
    api.get("/api/invoices").then(setInvoices).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const patch = async (id: number, body: any) => {
    await api.put(`/api/invoices/${id}`, body);
    load();
  };

  return (
    <div className="fade-up space-y-4">
      <PageHeader title="Invoices"
        sub="Created from job field entries (Jobs page) — holdbacks tracked until release" />
      {error && <p className="rounded-xl bg-bad/10 px-4 py-2 text-sm text-bad">{error}</p>}

      {invoices.length === 0 ? (
        <EmptyState>No invoices yet — open a job and click
          “Invoice unbilled entries”.</EmptyState>
      ) : (
        <Table head={<>
          <Th>Number</Th><Th>Client</Th><Th>Job</Th><Th>Date</Th><Th>Status</Th>
          <Th right>Subtotal</Th><Th right>GST</Th><Th right>Holdback</Th>
          <Th right>Due now</Th><Th right> </Th>
        </>}>
          {invoices.map((inv) => (
            <tr key={inv.id} className="hover:bg-surface-2">
              <Td className="font-medium">{inv.number}</Td>
              <Td>{inv.client_name}</Td>
              <Td className="text-xs">{inv.job_number}</Td>
              <Td>{inv.date}</Td>
              <Td>
                <Select value={inv.status} className="!w-auto !py-1 text-xs"
                  onChange={(e) => patch(inv.id, { status: e.target.value })}>
                  {["draft", "sent", "paid", "void"].map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Td>
              <Td right>{money(inv.subtotal)}</Td>
              <Td right>{money(inv.gst)}</Td>
              <Td right>
                {inv.holdback > 0 ? (
                  <button
                    title={inv.holdback_released ? "Holdback released"
                      : "Click to release holdback"}
                    onClick={() => !inv.holdback_released &&
                      confirm(`Release ${money(inv.holdback)} holdback on ${inv.number}?`) &&
                      patch(inv.id, { holdback_released: true })}>
                    <Badge tone={inv.holdback_released ? "good" : "warn"}>
                      {inv.holdback_released ? <LockOpen size={11} /> : <Lock size={11} />}
                      &nbsp;{money(inv.holdback)}
                    </Badge>
                  </button>
                ) : "—"}
              </Td>
              <Td right className="font-semibold">{money(inv.amount_due_now)}</Td>
              <Td right>
                <div className="flex justify-end gap-0.5">
                  <button className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink-1"
                    title="Download PDF"
                    onClick={() => api.download(`/api/invoices/${inv.id}/pdf`, `${inv.number}.pdf`)}>
                    <Download size={14} />
                  </button>
                  <button className="rounded-lg p-1.5 text-ink-3 hover:bg-bad/10 hover:text-bad"
                    title="Delete (releases billed entries)"
                    onClick={async () => {
                      if (confirm(`Delete ${inv.number}? Its job entries become billable again.`)) {
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
    </div>
  );
}
