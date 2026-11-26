import { useMemo, useState } from "react";
import { api, getSession } from "../api";
import { Chart } from "../components/Chart";
import { Card, DataTable, Drawer, ErrorBox, Loading, PageHead, Sev, Status, Tabs, toast, useApi } from "../components/ui";
import type { Assessment, Control, Rule, Severity } from "../types";

function cellClass(r: string) {
  return r === "Effective" ? "r-Effective" : r === "Partially Effective" ? "r-Partially" : r === "Ineffective" ? "r-Ineffective" : "r-NA";
}

export default function Controls() {
  const rules = useApi<Rule[]>("/api/rules");
  const controls = useApi<Control[]>("/api/controls");
  const assess = useApi<Assessment[]>("/api/assessments");
  const [tab, setTab] = useState("Assessment matrix");
  const [cycle, setCycle] = useState("");
  const [open, setOpen] = useState<Assessment | null>(null);
  const [evidence, setEvidence] = useState<any[] | null>(null);
  const [running, setRunning] = useState(false);
  const role = getSession()?.role;

  const cycles = useMemo(() => Array.from(new Set((assess.data ?? []).map((a) => a.cycle))).sort(), [assess.data]);
  const cur = cycle || cycles.at(-1) || "";
  const latest = useMemo(() => {
    const m = new Map<string, Assessment>();
    (assess.data ?? []).filter((a) => a.cycle === cur).forEach((a) => m.set(`${a.control_code}|${a.jurisdiction}`, a));
    return m;
  }, [assess.data, cur]);
  const trend = useMemo(() => cycles.map((c) => {
    const last = new Map<string, Assessment>();  // latest run per control x jurisdiction within the cycle
    (assess.data ?? []).filter((a) => a.cycle === c).forEach((a) => last.set(`${a.control_code}|${a.jurisdiction}`, a));
    const xs = [...last.values()].filter((a) => a.result !== "Not Applicable");
    return { c, eff: (100 * xs.filter((a) => a.result === "Effective").length) / Math.max(1, xs.length), n: xs.length };
  }), [assess.data, cycles]);

  const err = rules.error || controls.error || assess.error;
  if (err) return <ErrorBox error={err} />;
  if (!rules.data || !controls.data || !assess.data) return <Loading />;
  const jurs = Array.from(new Set(assess.data.map((a) => a.jurisdiction).filter((j) => j !== "EMEA"))).sort();

  const openCell = async (a: Assessment) => {
    setOpen(a); setEvidence(null);
    try { setEvidence((await api.get<{ evidence: any[] }>(`/api/assessments/${a.id}`)).evidence); } catch (e: any) { toast(e.message, true); }
  };
  const run = async () => {
    setRunning(true);
    try {
      const r = await api.post<{ assessments: number; results: Record<string, number>; demo?: boolean }>("/api/assessments/run", {});
      toast(`${r.assessments} control assessments ${r.demo ? "(latest stored cycle, demo)" : "completed"}: ${Object.entries(r.results).map(([k, v]) => `${v} ${k}`).join(", ")}`);
      assess.reload();
    } catch (e: any) { toast(e.message, true); } finally { setRunning(false); }
  };
  const toggle = async (r: Rule, patch: Partial<Rule>) => {
    try {
      const upd = await api.patch<Rule>(`/api/rules/${r.code}`, patch);
      rules.setData(rules.data!.map((x) => (x.code === r.code ? { ...x, ...upd } : x)));
      toast(`${r.code} updated. New access requests use the new configuration.`);
    } catch (e: any) { toast(e.message, true); }
  };

  return (
    <>
      <PageHead title="Control assessments" desc={`A configurable control engine: ${rules.data.length} access rules evaluated on every request, plus ${controls.data.length} automated control tests run per jurisdiction each cycle (${assess.data.length} assessments on record). Failing controls raise gaps; controls that pass on retest auto-close them.`}
        actions={<button className="primary" onClick={run} disabled={running || role === "auditor"}>{running ? "Running…" : "Run control tests now"}</button>} />
      <Tabs tabs={["Assessment matrix", "Governance rules", "Control library"]} value={tab} onChange={setTab} />

      {tab === "Assessment matrix" && (
        <div className="grid split split-320">
          <Card title="Pass rate by control and jurisdiction" right={<select value={cur} onChange={(e) => setCycle(e.target.value)}>{cycles.map((c) => <option key={c}>{c}</option>)}</select>}>
            <div className="legend" style={{ marginBottom: 8 }}><span><i className="r-Effective" />Effective</span><span><i className="r-Partially" />Partially effective</span><span><i className="r-Ineffective" />Ineffective</span><span><i className="r-NA" />Not applicable</span><span className="faint">Click a cell for evidence</span></div>
            <div style={{ overflowX: "auto" }}>
              <table className="heat">
                <thead><tr><th>Control</th>{jurs.map((j) => <th key={j} style={{ textAlign: "center" }}>{j}</th>)}<th style={{ textAlign: "center" }}>EMEA</th></tr></thead>
                <tbody>{controls.data.map((c) => (
                  <tr key={c.code}>
                    <td style={{ whiteSpace: "nowrap" }}><span className="mono">{c.code}</span> <span className="faint">{c.name}</span></td>
                    {[...jurs, "EMEA"].map((j) => {
                      const a = latest.get(`${c.code}|${j}`);
                      if (!a) return <td key={j} className="cell r-NA" style={{ cursor: "default" }} />;
                      return <td key={j} className={`cell ${cellClass(a.result)}`} title={`${a.result}: ${a.exceptions}/${a.population} exceptions`} onClick={() => openCell(a)}>
                        {a.result === "Not Applicable" ? "n/a" : `${a.pass_rate.toFixed(0)}%`}</td>;
                    })}
                  </tr>))}
                </tbody>
              </table>
            </div>
          </Card>
          <Card title="Controls effective by cycle">
            <Chart height={240} data={[{ type: "bar", x: trend.map((t) => t.c), y: trend.map((t) => t.eff), marker: { color: "#257de0" },
              text: trend.map((t) => `${t.eff.toFixed(0)}%`), textposition: "outside", cliponaxis: false,
              hovertemplate: "%{x}: %{y:.1f}% effective<extra></extra>" }]} layout={{ yaxis: { range: [0, 100], ticksuffix: "%" } }} />
            <div className="faint">Share of applicable control assessments rated Effective. Remediation between cycles closes gaps; time-based tests (training expiry, mechanism expiry, dormancy) open new ones.</div>
          </Card>
        </div>
      )}

      {tab === "Governance rules" && (
        <Card title="Access decision rules" sub={role === "admin" ? "admin: toggle rules or change severity; changes are audited" : "sign in as admin to reconfigure"}>
          <DataTable rows={rules.data.map((r) => ({ ...r, id: r.code }))} cols={[
            { key: "code", label: "Rule", render: (r) => <span className="mono">{r.code}</span> },
            { key: "name", label: "Name", render: (r) => <>{r.name}<div className="faint">{r.description}</div></> },
            { key: "category", label: "Category" },
            { key: "severity", label: "Severity", render: (r) => role === "admin" ? (
              <select value={r.severity} onChange={(e) => toggle(r, { severity: e.target.value as Severity })}>{["Critical", "High", "Medium", "Low"].map((s) => <option key={s}>{s}</option>)}</select>) : <Sev s={r.severity} /> },
            { key: "effect", label: "Effect", render: (r) => <>{r.effect}{r.raises_gap ? <div className="faint">raises gap</div> : null}</> },
            { key: "requirement_codes", label: "Maps to", render: (r) => <span className="faint">{r.requirement_codes.join(", ")}</span> },
            { key: "enabled", label: "Enabled", render: (r) => <label className="check"><input type="checkbox" checked={r.enabled} disabled={role !== "admin"} onChange={(e) => toggle(r, { enabled: e.target.checked })} />{r.enabled ? "On" : "Off"}</label> },
          ]} />
        </Card>
      )}

      {tab === "Control library" && (
        <Card title="Control library">
          <DataTable rows={controls.data} cols={[
            { key: "code", label: "Control", render: (c) => <span className="mono">{c.code}</span> },
            { key: "name", label: "Name", render: (c) => <>{c.name}<div className="faint">{c.description}</div></> },
            { key: "domain", label: "Domain" }, { key: "control_type", label: "Type" },
            { key: "criticality", label: "Criticality", num: true }, { key: "threshold", label: "Threshold", num: true, render: (c) => `${c.threshold}%` },
            { key: "frequency", label: "Frequency" }, { key: "scope", label: "Scope" },
            { key: "requirements", label: "Requirements", render: (c) => <span className="faint">{c.requirements.join(", ")}</span> },
          ]} />
        </Card>
      )}

      {open && (
        <Drawer title={`${open.control_code} ${open.control_name} · ${open.jurisdiction}`} sub={`Cycle ${open.cycle} · as of ${open.as_of}`} onClose={() => setOpen(null)}>
          <div className="row" style={{ marginBottom: 12 }}><Status s={open.result} /><Sev s={open.severity} />
            <span className="muted">{open.exceptions} exception(s) in a population of {open.population} · pass rate {open.pass_rate}%</span></div>
          {evidence === null ? <Loading what="evidence" /> : evidence.length ? (
            <DataTable rows={evidence.map((e, i) => ({ ...e, id: i }))} cols={[
              { key: "entity", label: "Type" }, { key: "label", label: "Item", render: (e) => <span className="mono">{e.label}</span> }, { key: "reason", label: "Exception" },
            ]} />) : <div className="empty">No exceptions: the control operated effectively.</div>}
        </Drawer>
      )}
    </>
  );
}

