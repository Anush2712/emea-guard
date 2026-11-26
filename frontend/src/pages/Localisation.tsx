import { useState } from "react";
import { Card, DataTable, ErrorBox, fmtDate, Kpi, Loading, PageHead, Status, Tabs, uniq, useApi } from "../components/ui";
import type { Jurisdiction, LocalisationRecord, TransferMechanism } from "../types";

export default function Localisation() {
  const recs = useApi<LocalisationRecord[]>("/api/localisation/records");
  const mechs = useApi<TransferMechanism[]>("/api/localisation/transfer-mechanisms");
  const adequacy = useApi<Record<string, Record<string, boolean>>>("/api/transfers/adequacy-matrix");
  const jurs = useApi<Jurisdiction[]>("/api/jurisdictions");
  const [tab, setTab] = useState("Residency & transfer monitoring");
  const [status, setStatus] = useState("issues");
  const [j, setJ] = useState("");
  const err = recs.error || mechs.error || adequacy.error || jurs.error;
  if (err) return <ErrorBox error={err} />;
  if (!recs.data || !mechs.data || !adequacy.data || !jurs.data) return <Loading />;
  const issues = recs.data.filter((r) => ["Residency breach", "No transfer mechanism", "Mechanism expired", "TIA missing"].includes(r.status));
  const abroad = recs.data.filter((r) => r.asset_jurisdiction !== r.location_jurisdiction);
  const rows = recs.data.filter((r) => (status === "issues" ? issues.includes(r) : status === "abroad" ? abroad.includes(r) : !status || r.status === status) && (!j || r.asset_jurisdiction === j));
  const codes = jurs.data.map((x) => x.code).sort();
  const mechFor = (s: string, d: string) => mechs.data!.find((m) => m.source === s && m.destination === d);

  return (
    <>
      <PageHead title="Data localisation" desc="Where every copy of every asset lives (primary, replica, backup, DR), checked against residency rules, adequacy decisions and transfer mechanisms (SCCs, UK IDTA, intra-group agreements) with transfer impact assessments." />
      <div className="grid g4">
        <Kpi label="Storage locations monitored" value={recs.data.length} hint={`${new Set(recs.data.map((r) => r.asset_id)).size} assets`} />
        <Kpi label="Copies held outside home jurisdiction" value={abroad.length} />
        <Kpi label="Localisation issues" value={issues.length} hint="Residency breaches, missing / expired mechanisms, missing TIA" />
        <Kpi label="Transfer mechanisms" value={mechs.data.length} hint={`${mechs.data.filter((m) => m.status !== "Valid").length} need attention`} />
      </div>
      <div className="mt"><Tabs tabs={["Residency & transfer monitoring", "Adequacy matrix", "Transfer mechanisms"]} value={tab} onChange={setTab} /></div>

      {tab === "Residency & transfer monitoring" && (
        <Card title="Storage locations">
          <div className="filters">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="issues">Issues only</option><option value="abroad">Held abroad</option><option value="">All locations</option>
              {uniq(recs.data.map((r) => r.status)).map((s) => <option key={s}>{s}</option>)}
            </select>
            <select value={j} onChange={(e) => setJ(e.target.value)}><option value="">All home jurisdictions</option>{codes.map((c) => <option key={c}>{c}</option>)}</select>
          </div>
          <DataTable rows={rows} cols={[
            { key: "asset_ref", label: "Asset", render: (r) => <><span className="mono">{r.asset_ref}</span> <span className="faint">{r.asset_name}</span></> },
            { key: "asset_jurisdiction", label: "Home" },
            { key: "location_jurisdiction", label: "Stored in" },
            { key: "location_type", label: "Copy" },
            { key: "hosting_region", label: "Hosting region" },
            { key: "personal_data", label: "Personal", render: (r) => (r.personal_data ? "Yes" : "No") },
            { key: "residency_required", label: "Residency", render: (r) => (r.residency_required ? "Restricted" : "—") },
            { key: "status", label: "Status", render: (r) => <Status s={r.status} /> },
            { key: "issue", label: "Issue", render: (r) => <span style={{ fontSize: 12.5 }}>{r.issue ?? ""}</span> },
          ]} />
        </Card>
      )}

      {tab === "Adequacy matrix" && (
        <Card title="Can personal data held in the row jurisdiction be exposed to someone in the column jurisdiction?" sub="simplified model, see docs/REGULATORY_MODEL.md">
          <div className="legend" style={{ marginBottom: 10 }}>
            <span><i className="a-yes" />✓ Adequate (no extra safeguard)</span><span><i className="a-mech" />M Valid mechanism</span><span><i className="a-no" />✕ Needs mechanism / expired</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="adequacy" style={{ width: "auto" }}>
              <thead><tr><th>Data in ↓ / Access from →</th>{codes.map((c) => <th key={c} style={{ textAlign: "center" }}>{c}</th>)}</tr></thead>
              <tbody>{codes.map((s) => (
                <tr key={s}><th>{s} · {jurs.data!.find((x) => x.code === s)?.name}</th>
                  {codes.map((d) => {
                    if (s === d) return <td key={d} className="cell a-self">—</td>;
                    if (adequacy.data![s]?.[d]) return <td key={d} className="cell a-yes" title={`${s} → ${d}: adequate`}>✓</td>;
                    const m = mechFor(s, d);
                    const ok = m && m.status !== "Expired" && m.tia_completed;
                    return <td key={d} className={`cell ${ok ? "a-mech" : "a-no"}`} title={m ? `${m.reference} · ${m.status}` : "No mechanism"}>{ok ? "M" : "✕"}</td>;
                  })}
                </tr>))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === "Transfer mechanisms" && (
        <Card title="Transfer mechanisms register">
          <DataTable rows={mechs.data} cols={[
            { key: "reference", label: "Reference", render: (m) => <span className="mono">{m.reference}</span> },
            { key: "source", label: "From" }, { key: "destination", label: "To" }, { key: "mechanism", label: "Mechanism" },
            { key: "valid_from", label: "Valid from", render: (m) => fmtDate(m.valid_from) },
            { key: "valid_until", label: "Valid until", render: (m) => fmtDate(m.valid_until) },
            { key: "tia_completed", label: "TIA", render: (m) => (m.tia_completed ? "Completed" : "Missing") },
            { key: "status", label: "Status", render: (m) => <Status s={m.status} /> },
          ]} />
        </Card>
      )}
    </>
  );
}
