import { useState } from "react";
import { Bar, Card, DataTable, ErrorBox, fmtDate, Loading, PageHead, Status, Tabs, uniq, useApi } from "../components/ui";
import type { Project, Stakeholder } from "../types";

export default function Stakeholders() {
  const people = useApi<Stakeholder[]>("/api/stakeholders");
  const projects = useApi<Project[]>("/api/projects");
  const [tab, setTab] = useState("Ownership & workload");
  const [fn, setFn] = useState("");
  if (people.error || projects.error) return <ErrorBox error={(people.error || projects.error)!} />;
  if (!people.data || !projects.data) return <Loading />;
  const rows = people.data.filter((s) => !fn || s.function === fn);
  return (
    <>
      <PageHead title="Stakeholders & projects" desc="Who owns what: accountable data owners, jurisdiction DPOs and data stewards, control owners and executives, with their live gap and remediation workload, plus the governance programmes in flight." />
      <Tabs tabs={["Ownership & workload", "Projects"]} value={tab} onChange={setTab} />
      {tab === "Ownership & workload" ? (
        <Card title="Stakeholders" right={<select value={fn} onChange={(e) => setFn(e.target.value)}><option value="">All functions</option>{uniq(people.data.map((s) => s.function)).map((x) => <option key={x}>{x}</option>)}</select>}>
          <DataTable rows={rows} cols={[
            { key: "name", label: "Name", render: (s) => <><b>{s.name}</b><div className="faint">{s.title}</div></> },
            { key: "function", label: "Function" }, { key: "jurisdiction", label: "Jur.", render: (s) => s.jurisdiction ?? "EMEA" },
            { key: "assets_owned", label: "Assets owned", num: true }, { key: "open_gaps", label: "Open gaps", num: true },
            { key: "critical_high", label: "Critical/High", num: true }, { key: "overdue", label: "Overdue", num: true, render: (s) => <span style={{ color: s.overdue ? "#a3191a" : undefined }}>{s.overdue}</span> },
            { key: "open_tasks", label: "Open tasks", num: true }, { key: "email", label: "Email", render: (s) => <span className="faint">{s.email}</span> },
          ]} />
        </Card>
      ) : (
        <div className="grid g2">
          {projects.data.map((p) => (
            <Card key={p.id} title={`${p.code} · ${p.name}`} right={<Status s={p.status} />}>
              <p className="muted" style={{ marginTop: 0 }}>{p.description}</p>
              <div className="row" style={{ marginBottom: 10 }}><span className="faint">Sponsor {p.sponsor} · {fmtDate(p.start_date)} → {fmtDate(p.target_date)}</span></div>
              <div className="row" style={{ marginBottom: 12 }}><div style={{ flex: 1 }}><Bar pct={p.progress} /></div><b>{p.progress}%</b></div>
              <table><tbody>{p.activities.map((a) => (
                <tr key={a.id}><td>{a.title}<div className="faint">{a.type}</div></td><td style={{ whiteSpace: "nowrap" }}>{fmtDate(a.due_date)}</td><td><Status s={a.status} /></td></tr>
              ))}</tbody></table>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
