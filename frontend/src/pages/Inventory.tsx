import { useState } from "react";
import { Card, DataTable, ErrorBox, fmtDate, Loading, PageHead, Status, Tabs, uniq, useApi } from "../components/ui";
import type { Asset, Employee, Role } from "../types";

const yes = (b: boolean) => (b ? "Yes" : "—");

export default function Inventory() {
  const assets = useApi<Asset[]>("/api/assets");
  const emps = useApi<Employee[]>("/api/employees");
  const roles = useApi<Role[]>("/api/roles");
  const [tab, setTab] = useState("Data assets");
  const [j, setJ] = useState(""); const [q, setQ] = useState(""); const [d, setD] = useState("");
  const err = assets.error || emps.error || roles.error;
  if (err) return <ErrorBox error={err} />;
  if (!assets.data || !emps.data || !roles.data) return <Loading />;
  const match = (s: string) => !q || s.toLowerCase().includes(q.toLowerCase());
  return (
    <>
      <PageHead title="Data & people" desc={`Register of ${assets.data.length} data assets and ${emps.data.length} synthetic employees across ${roles.data.length} RBAC roles. Defects (unowned, unclassified, unencrypted, over-retained assets; stale training; leavers) are seeded deliberately so the controls have something to find.`} />
      <Tabs tabs={["Data assets", "Employees", "Roles & permissions"]} value={tab} onChange={(t) => { setTab(t); setD(""); }} />
      {tab !== "Roles & permissions" && (
        <div className="filters">
          <input type="search" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={j} onChange={(e) => setJ(e.target.value)}><option value="">All jurisdictions</option>{uniq(assets.data.map((a) => a.jurisdiction)).map((x) => <option key={x}>{x}</option>)}</select>
          {tab === "Data assets"
            ? <select value={d} onChange={(e) => setD(e.target.value)}><option value="">All domains</option>{uniq(assets.data.map((a) => a.domain)).map((x) => <option key={x}>{x}</option>)}</select>
            : <select value={d} onChange={(e) => setD(e.target.value)}><option value="">All roles</option>{uniq(emps.data.map((e) => e.role)).map((x) => <option key={x}>{x}</option>)}</select>}
        </div>
      )}
      {tab === "Data assets" && (
        <Card title="Data asset register">
          <DataTable rows={assets.data.filter((a) => (!j || a.jurisdiction === j) && (!d || a.domain === d) && match(`${a.asset_ref} ${a.name} ${a.system}`))} cols={[
            { key: "asset_ref", label: "Asset", render: (a) => <span className="mono">{a.asset_ref}</span> },
            { key: "name", label: "Name", render: (a) => <>{a.name}<div className="faint">{a.system} · {a.hosting_provider}</div></> },
            { key: "jurisdiction", label: "Jur." }, { key: "domain", label: "Domain" },
            { key: "classification", label: "Classification", render: (a) => <span className={`badge ${a.classification_level ? "b-neutral" : "b-bad"}`}>{a.classification}</span>, sort: (a) => a.classification_level ?? 9 },
            { key: "owner", label: "Owner", render: (a) => a.owner ?? <span className="badge b-bad">Unowned</span> },
            { key: "contains_personal_data", label: "Personal", render: (a) => yes(a.contains_personal_data) },
            { key: "contains_cid", label: "CID", render: (a) => yes(a.contains_cid) },
            { key: "residency_required", label: "Residency", render: (a) => yes(a.residency_required) },
            { key: "encrypted_at_rest", label: "Encrypted", render: (a) => (a.encrypted_at_rest ? "Yes" : <span className="badge b-bad">No</span>) },
            { key: "record_count", label: "Records", num: true, render: (a) => a.record_count.toLocaleString("en-IE") },
            { key: "locations", label: "Copies", num: true, render: (a) => a.locations.length, sort: (a) => a.locations.length },
          ]} />
        </Card>
      )}
      {tab === "Employees" && (
        <Card title="Employees">
          <DataTable rows={emps.data.filter((e) => (!j || e.jurisdiction === j) && (!d || e.role === d) && match(`${e.employee_ref} ${e.full_name} ${e.business_unit}`))} cols={[
            { key: "employee_ref", label: "ID", render: (e) => <span className="mono">{e.employee_ref}</span> },
            { key: "full_name", label: "Name" }, { key: "jurisdiction", label: "Jur." }, { key: "role", label: "Role", render: (e) => <>{e.role}{e.role_privileged && <span className="badge b-warn" style={{ marginLeft: 6 }}>privileged</span>}</> },
            { key: "business_unit", label: "Business unit" },
            { key: "status", label: "Status", render: (e) => <Status s={e.status} /> },
            { key: "last_training_date", label: "Training", render: (e) => fmtDate(e.last_training_date) },
            { key: "termination_date", label: "Left", render: (e) => fmtDate(e.termination_date) },
          ]} />
        </Card>
      )}
      {tab === "Roles & permissions" && (
        <Card title="RBAC model" sub="permission = domain × maximum classification × access types">
          <DataTable rows={roles.data} cols={[
            { key: "name", label: "Role", render: (r) => <><b>{r.name}</b>{r.privileged && <span className="badge b-warn" style={{ marginLeft: 6 }}>privileged</span>}<div className="faint">{r.description}</div></> },
            { key: "permissions", label: "Permissions", render: (r) => (
              <div style={{ display: "grid", gap: 3 }}>{r.permissions.map((p, i) => <div key={i} style={{ fontSize: 12.5 }}><b>{p.domain === "*" ? "All domains" : p.domain}</b> · up to {["", "Public", "Internal", "Confidential", "Restricted"][p.max_classification]} · {p.access_types.join(", ")}</div>)}</div>) },
            { key: "staff", label: "Employees", num: true, render: (r) => emps.data!.filter((e) => e.role === r.name).length, sort: (r) => emps.data!.filter((e) => e.role === r.name).length },
          ]} />
        </Card>
      )}
    </>
  );
}
