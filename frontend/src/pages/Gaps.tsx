import { useState } from "react";
import { api, getSession } from "../api";
import { Card, DataTable, Drawer, ErrorBox, fmtDate, fmtDateTime, Kpi, Loading, PageHead, Sev, Status, Tabs, toast, uniq, useApi } from "../components/ui";
import type { Gap, Task } from "../types";

export default function Gaps() {
  const gaps = useApi<Gap[]>("/api/gaps");
  const tasks = useApi<Task[]>("/api/remediation-tasks");
  const [tab, setTab] = useState("Compliance gaps");
  const [status, setStatus] = useState("open");
  const [sev, setSev] = useState(""); const [j, setJ] = useState(""); const [src, setSrc] = useState(""); const [q, setQ] = useState("");
  const [open, setOpen] = useState<Gap | null>(null);
  const canWrite = getSession()?.role !== "auditor";
  if (gaps.error || tasks.error) return <ErrorBox error={(gaps.error || tasks.error)!} />;
  if (!gaps.data || !tasks.data) return <Loading />;

  const isOpen = (g: Gap) => g.status === "Open" || g.status === "In Remediation";
  const openGaps = gaps.data.filter(isOpen);
  const rows = gaps.data.filter((g) => (status === "open" ? isOpen(g) : !status || g.status === status) && (!sev || g.severity === sev) &&
    (!j || g.jurisdiction === j) && (!src || g.source === src) && (!q || `${g.gap_ref} ${g.title} ${g.owner}`.toLowerCase().includes(q.toLowerCase())));

  const act = async (g: Gap, kind: "remediate" | "status", body?: any) => {
    try {
      const upd = kind === "remediate" ? await api.post<Gap>(`/api/gaps/${g.id}/remediate`) : await api.patch<Gap>(`/api/gaps/${g.id}`, body);
      gaps.setData(gaps.data!.map((x) => (x.id === g.id ? upd : x)));
      setOpen(upd);
      toast(`${g.gap_ref} → ${upd.status}`);
      tasks.reload();
    } catch (e: any) { toast(e.message, true); }
  };
  const setTask = async (t: Task, status: string) => {
    try {
      const upd = await api.patch<Task>(`/api/remediation-tasks/${t.id}`, { status });
      tasks.setData(tasks.data!.map((x) => (x.id === t.id ? { ...x, ...upd } : x)));
      toast(`${t.task_ref} → ${status}`);
    } catch (e: any) { toast(e.message, true); }
  };
  const openTasks = tasks.data.filter((t) => t.status !== "Completed");
  const today = new Date().toISOString().slice(0, 10);

  return (
    <>
      <PageHead title="Gaps & remediation" desc="Every failed detective control becomes a de-duplicated compliance gap, scored on a 4-level impact × likelihood matrix, routed to the accountable stakeholder and given a severity-based deadline (Critical 7d, High 30d, Medium 60d, Low 90d)." />
      <div className="grid g4">
        <Kpi label="Open gaps" value={openGaps.length} hint={`${gaps.data.length} identified in total`} />
        <Kpi label="Critical / High open" value={openGaps.filter((g) => g.severity === "Critical" || g.severity === "High").length} />
        <Kpi label="Overdue" value={openGaps.filter((g) => g.overdue).length} hint="Past remediation SLA" />
        <Kpi label="Resolved" value={gaps.data.filter((g) => g.status === "Resolved").length} hint="Including auto-closure on control retest" />
      </div>
      <div className="mt"><Tabs tabs={["Compliance gaps", "Remediation tasks"]} value={tab} onChange={setTab} /></div>

      {tab === "Compliance gaps" ? (
        <Card title="Compliance gaps">
          <div className="filters">
            <input type="search" placeholder="Search gaps, owners…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">Open + in remediation</option><option value="">All statuses</option>{["Open", "In Remediation", "Resolved", "Risk Accepted"].map((s) => <option key={s}>{s}</option>)}</select>
            <select value={sev} onChange={(e) => setSev(e.target.value)}><option value="">All severities</option>{["Critical", "High", "Medium", "Low"].map((s) => <option key={s}>{s}</option>)}</select>
            <select value={j} onChange={(e) => setJ(e.target.value)}><option value="">All jurisdictions</option>{uniq(gaps.data.map((g) => g.jurisdiction)).map((x) => <option key={x}>{x}</option>)}</select>
            <select value={src} onChange={(e) => setSrc(e.target.value)}><option value="">All sources</option><option value="access_check">Access checks</option><option value="control_assessment">Control assessments</option></select>
          </div>
          <DataTable rows={rows} onRow={setOpen} selectedId={open?.id} cols={[
            { key: "gap_ref", label: "Gap", render: (g) => <span className="mono">{g.gap_ref}</span> },
            { key: "severity", label: "Severity", render: (g) => <Sev s={g.severity} />, sort: (g) => ["Low", "Medium", "High", "Critical"].indexOf(g.severity) },
            { key: "jurisdiction", label: "Jur." },
            { key: "title", label: "Finding", render: (g) => <>{g.title}{g.occurrences > 1 && <span className="faint"> · seen {g.occurrences}×</span>}</> },
            { key: "source", label: "Source", render: (g) => (g.source === "access_check" ? `Access check ${g.rule_code}` : `Control ${g.control_code}`) },
            { key: "owner", label: "Owner", render: (g) => <>{g.owner}<div className="faint">{g.owner_title}</div></> },
            { key: "due_date", label: "Due", render: (g) => <span style={{ color: g.overdue ? "#a3191a" : undefined }}>{fmtDate(g.due_date)}{g.overdue ? " · overdue" : ""}</span> },
            { key: "status", label: "Status", render: (g) => <Status s={g.status} /> },
          ]} />
        </Card>
      ) : (
        <Card title="Remediation tasks" sub={`${openTasks.length} open`}>
          <DataTable rows={tasks.data} cols={[
            { key: "task_ref", label: "Task", render: (t) => <span className="mono">{t.task_ref}</span> },
            { key: "gap_ref", label: "Gap", render: (t) => <span className="mono">{t.gap_ref}</span> },
            { key: "priority", label: "Priority", render: (t) => <Sev s={t.priority} />, sort: (t) => ["Low", "Medium", "High", "Critical"].indexOf(t.priority) },
            { key: "jurisdiction", label: "Jur." },
            { key: "title", label: "Action", render: (t) => <>{t.title}<div className="faint">{t.action}</div></> },
            { key: "owner", label: "Owner" },
            { key: "due_date", label: "Due", render: (t) => <span style={{ color: t.status !== "Completed" && t.due_date < today ? "#a3191a" : undefined }}>{fmtDate(t.due_date)}</span> },
            { key: "status", label: "Status", render: (t) => canWrite && t.status !== "Completed" ? (
              <select value={t.status} onChange={(e) => setTask(t, e.target.value)}>{["Not Started", "In Progress", "Completed"].map((s) => <option key={s}>{s}</option>)}</select>) : <Status s={t.status} /> },
          ]} />
        </Card>
      )}

      {open && (
        <Drawer title={`${open.gap_ref} · ${open.title}`} sub={`${open.jurisdiction} · identified ${fmtDateTime(open.identified_at)}`} onClose={() => setOpen(null)}>
          <div className="row" style={{ marginBottom: 14 }}><Sev s={open.severity} /><Status s={open.status} />{open.overdue && <span className="badge b-bad">Overdue</span>}</div>
          <dl className="kv">
            <dt>Finding</dt><dd>{open.description}</dd>
            <dt>Source</dt><dd>{open.source === "access_check" ? `Access check, rule ${open.rule_code}` : `Control assessment ${open.control_code}`}</dd>
            <dt>Severity basis</dt><dd>Impact {open.impact} × likelihood {open.likelihood} = {open.impact * open.likelihood} → {open.severity}</dd>
            <dt>Accountable owner</dt><dd>{open.owner} <span className="faint">{open.owner_title}</span></dd>
            <dt>Due (SLA)</dt><dd>{fmtDate(open.due_date)}</dd>
            <dt>Occurrences</dt><dd>{open.occurrences} (de-duplicated on the underlying weakness)</dd>
            {open.resolution_note && <><dt>Resolution</dt><dd>{open.resolution_note} {open.resolved_at && <span className="faint">({fmtDateTime(open.resolved_at)})</span>}</dd></>}
          </dl>
          <h3 className="mt" style={{ marginBottom: 8 }}>Remediation plan</h3>
          {open.tasks.map((t) => <div key={t.id} className="card" style={{ padding: 12, marginBottom: 8 }}><div className="row"><span className="mono">{t.task_ref}</span><Status s={t.status} /><span className="faint">due {fmtDate(t.due_date)} · {t.owner}</span></div><div style={{ marginTop: 6 }}>{t.action}</div></div>)}
          {canWrite && (open.status === "Open" || open.status === "In Remediation") && (
            <div className="row mt">
              {open.status === "Open" && <button onClick={() => act(open, "status", { status: "In Remediation" })}>Start remediation</button>}
              <button className="primary" onClick={() => act(open, "remediate")}>Apply corrective action & resolve</button>
              <button onClick={() => act(open, "status", { status: "Risk Accepted", note: "Risk accepted pending next review" })}>Accept risk</button>
            </div>
          )}
          {canWrite && (open.status === "Open" || open.status === "In Remediation") && <p className="faint">“Apply corrective action” changes the synthetic data (e.g. assigns the owner, renews the SCC, revokes the leaver's access). Re-run the control tests and the control will pass and stay closed.</p>}
        </Drawer>
      )}
    </>
  );
}
