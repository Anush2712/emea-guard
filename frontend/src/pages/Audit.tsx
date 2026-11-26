import { useState } from "react";
import { api } from "../api";
import { Card, DataTable, Drawer, ErrorBox, fmtDateTime, Loading, PageHead, toast, uniq, useApi } from "../components/ui";
import type { AuditEntry } from "../types";

export default function Audit() {
  const log = useApi<AuditEntry[]>("/api/audit?limit=5000");
  const [action, setAction] = useState(""); const [q, setQ] = useState(""); const [open, setOpen] = useState<AuditEntry | null>(null);
  const [verify, setVerify] = useState<{ valid: boolean; entries_checked: number; head?: string } | null>(null);
  if (log.error) return <ErrorBox error={log.error} />;
  if (!log.data) return <Loading />;
  const rows = log.data.filter((a) => (!action || a.action === action) && (!q || `${a.entity_id} ${a.actor} ${JSON.stringify(a.details)}`.toLowerCase().includes(q.toLowerCase())));
  const check = async () => { try { setVerify(await api.get("/api/audit/verify")); } catch (e: any) { toast(e.message, true); } };
  return (
    <>
      <PageHead title="Audit trail" desc="Append-only and hash-chained: every entry stores SHA-256(previous hash + canonical payload), so editing or deleting any historical record breaks the chain and is detected by verification."
        actions={<button className="primary" onClick={check}>Verify chain integrity</button>} />
      {verify && (
        <div className={`decision ${verify.valid ? "d-APPROVED" : "d-DENIED"}`} style={{ marginBottom: 16 }}>
          <div><div className="big">{verify.valid ? "✓ Chain intact" : "✕ Chain broken"}</div>
            <div style={{ fontSize: 12.5 }}>{verify.entries_checked} entries re-hashed{verify.head ? <> · head <span className="mono">{verify.head.slice(0, 20)}…</span></> : null}</div></div>
        </div>
      )}
      <Card title="Events" sub={`${log.data.length} entries`}>
        <div className="filters">
          <input type="search" placeholder="Search entity, actor, details…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={action} onChange={(e) => setAction(e.target.value)}><option value="">All actions</option>{uniq(log.data.map((a) => a.action)).map((x) => <option key={x}>{x}</option>)}</select>
        </div>
        <DataTable rows={rows} onRow={setOpen} cols={[
          { key: "id", label: "#", num: true },
          { key: "timestamp", label: "Time (UTC)", render: (a) => fmtDateTime(a.timestamp) },
          { key: "actor", label: "Actor" },
          { key: "action", label: "Action", render: (a) => <span className="mono">{a.action}</span> },
          { key: "entity_id", label: "Entity", render: (a) => <>{a.entity_type} <span className="mono">{a.entity_id}</span></> },
          { key: "jurisdiction", label: "Jur." },
          { key: "hash", label: "Hash", render: (a) => <span className="mono faint">{a.hash.slice(0, 12)}…</span> },
        ]} />
      </Card>
      {open && (
        <Drawer title={`#${open.id} · ${open.action}`} sub={`${fmtDateTime(open.timestamp)} · ${open.actor}`} onClose={() => setOpen(null)}>
          <dl className="kv">
            <dt>Entity</dt><dd>{open.entity_type} {open.entity_id}</dd>
            <dt>Jurisdiction</dt><dd>{open.jurisdiction ?? "—"}</dd>
            <dt>Previous hash</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{open.prev_hash}</dd>
            <dt>Entry hash</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{open.hash}</dd>
          </dl>
          <h3 className="mt">Details</h3>
          <pre className="doc">{JSON.stringify(open.details, null, 2)}</pre>
        </Drawer>
      )}
    </>
  );
}
