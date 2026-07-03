/** Generic entity page: quick-entry form + searchable, date-filtered table.
 * Each entity page provides a field config; the component handles list,
 * create, edit (modal), delete against the backend CRUD API. */
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import { useStore } from "../store";
import {
  Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, Table,
  Td, Th,
} from "./ui";

export type FieldDef = {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "select" | "checkbox";
  options?: string[] | { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
  step?: string;
  defaultValue?: unknown;
  span2?: boolean;
};

export type ColumnDef = {
  key: string;
  label: string;
  right?: boolean;
  render?: (row: any) => ReactNode;
};

function initialForm(fields: FieldDef[]): Record<string, any> {
  const f: Record<string, any> = {};
  for (const fd of fields) {
    f[fd.name] = fd.defaultValue ??
      (fd.type === "date" ? new Date().toISOString().slice(0, 10)
        : fd.type === "checkbox" ? false
        : fd.type === "select"
          ? (typeof fd.options?.[0] === "string" ? fd.options?.[0]
             : (fd.options?.[0] as any)?.value ?? "")
        : "");
  }
  return f;
}

export function EntityForm({ fields, value, onChange }: {
  fields: FieldDef[]; value: Record<string, any>;
  onChange: (v: Record<string, any>) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {fields.map((fd) => (
        <Field key={fd.name} label={fd.label}
          className={fd.span2 ? "col-span-2" : "col-span-2 sm:col-span-1"}>
          {fd.type === "select" ? (
            <Select value={value[fd.name] ?? ""} required={fd.required}
              onChange={(e) => onChange({ ...value, [fd.name]: e.target.value })}>
              {(fd.options ?? []).map((o) => {
                const v = typeof o === "string" ? o : o.value;
                const l = typeof o === "string" ? o : o.label;
                return <option key={v} value={v}>{l}</option>;
              })}
            </Select>
          ) : fd.type === "checkbox" ? (
            <label className="flex h-9 items-center gap-2 text-sm text-ink-1">
              <input type="checkbox" checked={!!value[fd.name]}
                onChange={(e) => onChange({ ...value, [fd.name]: e.target.checked })}
                className="size-4 accent-(--accent)" />
              Yes
            </label>
          ) : (
            <Input type={fd.type ?? "text"} value={value[fd.name] ?? ""}
              required={fd.required} placeholder={fd.placeholder} step={fd.step}
              onChange={(e) => onChange({
                ...value,
                [fd.name]: fd.type === "number"
                  ? (e.target.value === "" ? "" : Number(e.target.value))
                  : e.target.value,
              })} />
          )}
        </Field>
      ))}
    </div>
  );
}

export default function CrudPage({ title, sub, path, fields, columns,
  dateFiltered = true, footer, transform, prefill }: {
  title: string; sub?: string; path: string;
  fields: FieldDef[]; columns: ColumnDef[];
  dateFiltered?: boolean;
  footer?: (items: any[]) => ReactNode;
  transform?: (form: Record<string, any>) => Record<string, any>;
  /** Quick-pick templates: merged into the entry form when set (include a
   * changing key like _ts to re-trigger). */
  prefill?: Record<string, any> | null;
}) {
  const { period } = useStore();
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [form, setForm] = useState(() => initialForm(fields));
  const [editing, setEditing] = useState<any | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (dateFiltered) { p.set("start", period.start); p.set("end", period.end); }
    if (q) p.set("q", q);
    return p.toString();
  }, [dateFiltered, period, q]);

  const load = useCallback(() => {
    api.get(`${path}?${query}`)
      .then((r) => setItems(r.items ?? r))
      .catch((e) => setError(e.message));
  }, [path, query]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (prefill) {
      const { _ts, ...values } = prefill;
      setForm((f) => ({ ...f, ...values }));
    }
  }, [prefill]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const payload = transform ? transform(form) : form;
      await api.post(path, payload);
      setForm(initialForm(fields));
      load();
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  const saveEdit = async () => {
    setBusy(true); setError("");
    try {
      const payload = transform ? transform(editing) : editing;
      await api.put(`${path}/${editing.id}`, payload);
      setEditing(null);
      load();
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this entry? The audit log keeps a record.")) return;
    await api.del(`${path}/${id}`);
    load();
  };

  return (
    <div className="fade-up">
      <PageHeader title={title} sub={sub} />
      {error && <p className="mb-3 rounded-xl bg-bad/10 px-4 py-2 text-sm text-bad">{error}</p>}
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <Card title="Quick entry" className="h-fit">
          <form onSubmit={submit}>
            <EntityForm fields={fields} value={form} onChange={setForm} />
            <Button type="submit" disabled={busy} className="mt-4 w-full">
              <Plus size={16} /> Add entry
            </Button>
          </form>
        </Card>
        <div className="min-w-0 space-y-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
            <Input value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search…" className="pl-9" />
          </div>
          {items.length === 0 ? (
            <EmptyState>No entries {dateFiltered ? "in the selected period" : "yet"}.
              Add one with the quick-entry form.</EmptyState>
          ) : (
            <Table head={<>
              {columns.map((c) => <Th key={c.key} right={c.right}>{c.label}</Th>)}
              <Th right> </Th>
            </>}>
              {items.map((row) => (
                <tr key={row.id} className="hover:bg-surface-2">
                  {columns.map((c) => (
                    <Td key={c.key} right={c.right}>
                      {c.render ? c.render(row) : String(row[c.key] ?? "")}
                    </Td>
                  ))}
                  <Td right>
                    <div className="flex justify-end gap-0.5">
                      <button className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink-1"
                        onClick={() => setEditing({ ...row })} title="Edit">
                        <Pencil size={14} />
                      </button>
                      <button className="rounded-lg p-1.5 text-ink-3 hover:bg-bad/10 hover:text-bad"
                        onClick={() => remove(row.id)} title="Delete">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
          )}
          {footer && items.length > 0 && footer(items)}
        </div>
      </div>
      {editing && (
        <Modal title={`Edit ${title.toLowerCase()}`} onClose={() => setEditing(null)}>
          <EntityForm fields={fields} value={editing} onChange={setEditing} />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={saveEdit} disabled={busy}>Save changes</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
