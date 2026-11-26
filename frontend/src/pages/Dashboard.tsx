import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Chart, MUTED, SERIES, SEV_COLOR } from "../components/Chart";
import { Card, DataTable, ErrorBox, fmtDate, fmtDateTime, Kpi, Loading, PageHead, Sev, Status, useApi } from "../components/ui";
import { SEVERITIES, type Dashboard as D, type Gap } from "../types";

export default function Dashboard() {
  const { data, error } = useApi<D>("/api/dashboard/summary");
  const nav = useNavigate();
  const [focus, setFocus] = useState<string>("");
  const trend = useMemo(() => {
    if (!data) return null;
    const by: Record<string, { x: string[]; y: number[] }> = {};
    data.risk_trend.forEach((r) => { (by[r.code] ??= { x: [], y: [] }).x.push(r.cycle); by[r.code].y.push(r.residual_score); });
    return by;
  }, [data]);
  if (error) return <ErrorBox error={error} />;
  if (!data || !trend) return <Loading what="dashboard" />;
  const k = data.kpis;
  const top = focus || data.risk_by_jurisdiction[0]?.code;
  const risk = [...data.risk_by_jurisdiction].reverse();

  return (
    <>
      <PageHead title="Governance dashboard"
        desc={<>Regional compliance and control health across 10 EMEA jurisdictions, as of {fmtDate(data.as_of)} (assessment cycle {k.latest_cycle}). All data is synthetic.</>}
        actions={<><button onClick={() => nav("/access?scenario=jd")} className="primary">Run the DE → IE access scenario</button><Link to="/risk"><button>Risk reports</button></Link></>} />

      <div className="grid g6">
        <Kpi label="Average residual risk" value={k.avg_residual_risk.toFixed(1)} unit="/100" hint="Inherent × control, gap, overdue, denial factors" />
        <Kpi label="Controls effective" value={k.control_effectiveness.toFixed(0)} unit="%" hint={`Latest cycle ${k.latest_cycle}`} />
        <Kpi label="Open compliance gaps" value={k.open_gaps} hint={`${k.critical_high_open} Critical or High`} />
        <Kpi label="Critical / High open" value={k.critical_high_open} hint="Prioritised for remediation" />
        <Kpi label="Overdue remediation" value={k.overdue_remediation} hint="Past severity SLA" />
        <Kpi label="Access denial rate" value={k.denial_rate.toFixed(1)} unit="%" hint={`${k.access_requests} requests evaluated`} />
      </div>

      <div className="grid g2 mt">
        <Card title="Residual risk by jurisdiction" sub="0–100, higher is riskier">
          <Chart height={330} data={[{
            type: "bar", orientation: "h", y: risk.map((r) => `${r.name} (${r.code})`), x: risk.map((r) => r.residual_score),
            marker: { color: risk.map((r) => SEV_COLOR[r.rating]) }, text: risk.map((r) => `${r.residual_score.toFixed(1)} · ${r.rating}`),
            textposition: "outside", cliponaxis: false,
            customdata: risk.map((r) => [r.control_effectiveness, r.open_gaps, r.drivers[0]?.label ?? ""]),
            hovertemplate: "<b>%{y}</b><br>Residual %{x:.1f}<br>Control effectiveness %{customdata[0]}%<br>Open gaps %{customdata[1]}<br>Top driver: %{customdata[2]}<extra></extra>",
          }]} layout={{ margin: { l: 170, r: 90, t: 4, b: 30 }, xaxis: { range: [0, 100] } }} />
          <div className="legend">{SEVERITIES.map((s) => <span key={s}><i style={{ background: SEV_COLOR[s] }} />{s}</span>)}</div>
        </Card>
        <Card title="Risk trend by quarter" right={
          <select value={top} onChange={(e) => setFocus(e.target.value)} aria-label="Highlight jurisdiction">
            {data.risk_by_jurisdiction.map((r) => <option key={r.code} value={r.code}>Highlight {r.name}</option>)}
          </select>}>
          <Chart height={330} data={[
            ...Object.entries(trend).filter(([c]) => c !== top).map(([c, t]) => ({
              type: "scatter" as const, mode: "lines" as const, x: t.x, y: t.y, name: c, line: { color: MUTED, width: 1.5 },
              hovertemplate: `${c} %{x}: %{y:.1f}<extra></extra>`,
            })),
            { type: "scatter", mode: "lines+markers", x: trend[top].x, y: trend[top].y, name: top, line: { color: SERIES[0], width: 2.5 },
              marker: { size: 8 }, hovertemplate: `<b>${top}</b> %{x}: %{y:.1f}<extra></extra>` },
          ]} layout={{ yaxis: { range: [0, 100], title: { text: "Residual risk" } }, annotations: [{
            x: trend[top].x.at(-1), y: trend[top].y.at(-1), text: `<b>${top}</b> ${trend[top].y.at(-1)?.toFixed(1)}`, showarrow: false, xanchor: "left", xshift: 8, font: { color: "#16202e" },
          }] }} />
          <div className="faint">Grey lines: other jurisdictions. Each point is a recalculation after a control assessment cycle.</div>
        </Card>
      </div>

      <div className="grid g3 mt">
        <Card title="Open gaps by severity">
          <Chart height={220} data={[{
            type: "bar", x: SEVERITIES, y: SEVERITIES.map((s) => data.gaps_by_severity[s] ?? 0), marker: { color: SEVERITIES.map((s) => SEV_COLOR[s]) },
            text: SEVERITIES.map((s) => String(data.gaps_by_severity[s] ?? 0)), textposition: "outside", cliponaxis: false,
            hovertemplate: "%{x}: %{y} open gaps<extra></extra>",
          }]} />
        </Card>
        <Card title="Access decisions" sub="2026 requests">
          <Chart height={220} data={[{
            type: "bar", orientation: "h", y: ["Denied", "Pending approval", "Approved · findings", "Approved"],
            x: ["DENIED", "PENDING_APPROVAL", "APPROVED_WITH_FINDINGS", "APPROVED"].map((d) => data.decisions[d] ?? 0),
            marker: { color: SERIES[0] }, text: ["DENIED", "PENDING_APPROVAL", "APPROVED_WITH_FINDINGS", "APPROVED"].map((d) => String(data.decisions[d] ?? 0)),
            textposition: "outside", cliponaxis: false, hovertemplate: "%{y}: %{x}<extra></extra>",
          }]} layout={{ margin: { l: 130, r: 40, t: 4, b: 30 } }} />
        </Card>
        <Card title="Control results" sub={`cycle ${k.latest_cycle}`}>
          <Chart height={220} data={[{
            type: "bar", orientation: "h", y: ["Ineffective", "Partially Effective", "Effective", "Not Applicable"],
            x: ["Ineffective", "Partially Effective", "Effective", "Not Applicable"].map((r) => data.control_results[r] ?? 0),
            marker: { color: [SEV_COLOR.Critical, SEV_COLOR.Medium, SEV_COLOR.Low, MUTED] },
            text: ["Ineffective", "Partially Effective", "Effective", "Not Applicable"].map((r) => String(data.control_results[r] ?? 0)),
            textposition: "outside", cliponaxis: false, hovertemplate: "%{y}: %{x}<extra></extra>",
          }]} layout={{ margin: { l: 130, r: 40, t: 4, b: 30 } }} />
        </Card>
      </div>

      <div className="grid g3 mt">
        <Card title="Priority open gaps" className="span2" right={<Link to="/gaps">All gaps →</Link>}>
          <DataTable<Gap> rows={data.top_gaps} onRow={() => nav("/gaps")} cols={[
            { key: "gap_ref", label: "Gap", render: (g) => <span className="mono">{g.gap_ref}</span> },
            { key: "severity", label: "Severity", render: (g) => <Sev s={g.severity} /> },
            { key: "jurisdiction", label: "Jur." },
            { key: "title", label: "Finding" },
            { key: "owner", label: "Owner" },
            { key: "due_date", label: "Due", render: (g) => <span style={{ color: g.overdue ? "#a3191a" : undefined }}>{fmtDate(g.due_date)}{g.overdue ? " · overdue" : ""}</span> },
            { key: "status", label: "Status", render: (g) => <Status s={g.status} /> },
          ]} />
        </Card>
        <Card title="Recent activity" right={<Link to="/audit">Audit trail →</Link>}>
          <div style={{ display: "grid", gap: 10 }}>
            {data.recent_activity.slice(0, 9).map((a, i) => (
              <div key={i} style={{ fontSize: 12.5, borderBottom: "1px solid #eef0f4", paddingBottom: 8 }}>
                <div><b>{a.action.replace(/_/g, " ").toLowerCase()}</b> · <span className="mono">{a.entity_id}</span></div>
                <div className="faint">{fmtDateTime(a.timestamp)} · {a.actor}{a.jurisdiction ? ` · ${a.jurisdiction}` : ""}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
