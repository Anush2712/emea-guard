import { useMemo, useState } from "react";
import { downloadReport, getSession, api } from "../api";
import { Chart, MUTED, SERIES, SEV_COLOR } from "../components/Chart";
import { Card, DataTable, ErrorBox, Loading, PageHead, Sev, toast, useApi } from "../components/ui";
import type { RiskRow } from "../types";

const FACTORS: [string, string][] = [["controls", "Control ineffectiveness"], ["gaps", "Open gap pressure"], ["overdue", "Overdue remediation"], ["denials", "Access denials"]];

export default function Risk() {
  const latest = useApi<RiskRow[]>("/api/risk/jurisdictions");
  const hist = useApi<RiskRow[]>("/api/risk/history");
  const [focus, setFocus] = useState("");
  const byJ = useMemo(() => {
    const m: Record<string, RiskRow[]> = {};
    (hist.data ?? []).forEach((r) => (m[r.jurisdiction] ??= []).push(r));
    return m;
  }, [hist.data]);
  if (latest.error || hist.error) return <ErrorBox error={(latest.error || hist.error)!} />;
  if (!latest.data || !hist.data) return <Loading />;
  const top = focus || latest.data[0]?.jurisdiction;
  const sorted = [...latest.data].reverse();
  const dl = async (n: string) => { try { await downloadReport(n); } catch (e: any) { toast(e.message, true); } };
  const recalc = async () => { try { await api.post("/api/risk/recalculate"); latest.reload(); hist.reload(); toast("Risk recalculated"); } catch (e: any) { toast(e.message, true); } };

  return (
    <>
      <PageHead title="Risk reporting" desc="Jurisdiction residual risk = inherent risk multiplier × (45% control ineffectiveness + 30% open-gap pressure + 15% overdue remediation + 10% access denial rate), rated on the same 4-level scale as gaps."
        actions={<>
          <button className="primary" onClick={() => dl("risk-report.xlsx")}>⬇ Excel risk report</button>
          <button onClick={() => dl("executive.html")}>⬇ Executive report (HTML)</button>
          <button onClick={() => dl("gaps.csv")}>⬇ Gaps CSV</button>
          {getSession()?.role !== "auditor" && <button onClick={recalc}>Recalculate</button>}
        </>} />

      <div className="grid g2">
        <Card title="What drives each jurisdiction's score" sub="weighted contribution">
          <Chart height={360} data={FACTORS.map(([k, label], i) => ({
            type: "bar" as const, orientation: "h" as const, name: label, y: sorted.map((r) => r.jurisdiction),
            x: sorted.map((r) => r.drivers.find((d) => d.factor === k)?.contribution ?? 0), marker: { color: SERIES[i], line: { color: "#fff", width: 2 } },
            customdata: sorted.map((r) => r.drivers.find((d) => d.factor === k)?.label ?? ""),
            hovertemplate: `<b>%{y}</b> · ${label}<br>+%{x:.1f} points<br>%{customdata}<extra></extra>`,
          }))} layout={{ barmode: "stack", showlegend: true, legend: { orientation: "h", y: -0.3, traceorder: "normal" }, margin: { l: 40, r: 10, t: 4, b: 96 }, xaxis: { title: { text: "Residual risk points", standoff: 6 } } }} />
        </Card>
        <Card title="Residual risk over time" right={<select value={top} onChange={(e) => setFocus(e.target.value)}>{latest.data.map((r) => <option key={r.jurisdiction} value={r.jurisdiction}>Highlight {r.name}</option>)}</select>}>
          <Chart height={360} data={[
            ...Object.entries(byJ).filter(([c]) => c !== top).map(([c, rows]) => ({ type: "scatter" as const, mode: "lines" as const, x: rows.map((r) => r.as_of), y: rows.map((r) => r.residual_score), line: { color: MUTED, width: 1.5 }, hovertemplate: `${c} %{x}: %{y:.1f}<extra></extra>` })),
            { type: "scatter", mode: "lines+markers", x: byJ[top]?.map((r) => r.as_of), y: byJ[top]?.map((r) => r.residual_score), line: { color: SERIES[0], width: 2.5 }, marker: { size: 8, color: byJ[top]?.map((r) => SEV_COLOR[r.rating]), line: { color: "#fff", width: 2 } },
              customdata: byJ[top]?.map((r) => [r.rating, r.control_effectiveness]), hovertemplate: `<b>${top}</b> %{x}<br>%{y:.1f} · %{customdata[0]}<br>Controls %{customdata[1]}% effective<extra></extra>` },
          ]} layout={{ yaxis: { range: [0, 100] }, shapes: [70, 50, 30].map((y) => ({ type: "line" as const, xref: "paper" as const, x0: 0, x1: 1, y0: y, y1: y, line: { color: "#e7e7e7", width: 1 } })),
            annotations: [[85, "Critical"], [60, "High"], [40, "Medium"], [15, "Low"]].map(([y, t]) => ({ xref: "paper" as const, x: 1, y: y as number, text: t as string, showarrow: false, xanchor: "right" as const, font: { color: "#8a93a3", size: 11 } })) }} />
          <div className="faint">Marker colour shows the rating at each point; bands mark the 4-level scale.</div>
        </Card>
      </div>

      <Card title="Jurisdiction risk register" className="mt">
        <DataTable rows={latest.data.map((r) => ({ ...r, id: r.jurisdiction }))} cols={[
          { key: "jurisdiction", label: "Jurisdiction", render: (r) => <><b>{r.jurisdiction}</b> {r.name}</> },
          { key: "residual_score", label: "Residual", num: true, render: (r) => r.residual_score.toFixed(1) },
          { key: "rating", label: "Rating", render: (r) => <Sev s={r.rating} />, sort: (r) => r.residual_score },
          { key: "inherent_risk", label: "Inherent ×", num: true },
          { key: "control_effectiveness", label: "Controls effective", num: true, render: (r) => `${r.control_effectiveness}%` },
          { key: "open_gap_score", label: "Gap pressure", num: true },
          { key: "overdue_ratio", label: "Overdue", num: true, render: (r) => `${(r.overdue_ratio * 100).toFixed(0)}%` },
          { key: "access_denial_rate", label: "Denials (180d)", num: true, render: (r) => `${(r.access_denial_rate * 100).toFixed(0)}%` },
          { key: "drivers", label: "Top driver", render: (r) => <span className="faint">{r.drivers[0]?.label}</span> },
        ]} />
      </Card>
    </>
  );
}
