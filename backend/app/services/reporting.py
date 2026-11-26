"""Reporting engine: SQL -> Pandas -> Excel / CSV / Plotly HTML risk reports."""
from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
from sqlalchemy.orm import Session

SEV_COLORS = {"Critical": "#dc3c3d", "High": "#f18a59", "Medium": "#fbb315", "Low": "#0aac23"}
SEV_ORDER = ["Critical", "High", "Medium", "Low"]

SQL = {
    "risk": """
        SELECT j.code AS jurisdiction, j.name, r.as_of, r.cycle, r.residual_score, r.rating,
               r.control_effectiveness, r.open_gap_score, r.overdue_ratio, r.access_denial_rate, j.inherent_risk
        FROM risk_assessments r JOIN jurisdictions j ON j.id = r.jurisdiction_id
        ORDER BY r.as_of, j.code""",
    "gaps": """
        SELECT g.gap_ref, COALESCE(j.code, 'EMEA') AS jurisdiction, g.source, COALESCE(g.rule_code, c.code) AS rule_or_control,
               g.title, g.severity, g.status, s.name AS owner, s.title AS owner_title, g.identified_at, g.due_date,
               g.resolved_at, g.occurrences, g.description
        FROM compliance_gaps g
        LEFT JOIN jurisdictions j ON j.id = g.jurisdiction_id
        LEFT JOIN governance_controls c ON c.id = g.control_id
        LEFT JOIN stakeholders s ON s.id = g.owner_id
        ORDER BY g.identified_at""",
    "assessments": """
        SELECT a.cycle, a.as_of, c.code AS control, c.name AS control_name, COALESCE(j.code, 'EMEA') AS jurisdiction,
               a.population, a.exceptions, a.pass_rate, a.result, a.severity
        FROM control_assessments a
        JOIN governance_controls c ON c.id = a.control_id
        LEFT JOIN jurisdictions j ON j.id = a.jurisdiction_id
        ORDER BY a.id""",
    "tasks": """
        SELECT t.task_ref, g.gap_ref, COALESCE(j.code, 'EMEA') AS jurisdiction, t.title, t.priority, t.status,
               s.name AS owner, t.due_date, t.completed_at
        FROM remediation_tasks t JOIN compliance_gaps g ON g.id = t.gap_id
        LEFT JOIN jurisdictions j ON j.id = g.jurisdiction_id
        LEFT JOIN stakeholders s ON s.id = t.owner_id
        ORDER BY t.due_date""",
    "access": """
        SELECT ar.request_ref, ar.requested_at, ej.code AS employee_jurisdiction, aj.code AS asset_jurisdiction,
               ar.access_type, ar.purpose, ar.decision, ar.risk_score, ar.risk_rating, ar.cross_border
        FROM access_requests ar
        JOIN employees e ON e.id = ar.employee_id JOIN jurisdictions ej ON ej.id = e.jurisdiction_id
        JOIN data_assets d ON d.id = ar.asset_id JOIN jurisdictions aj ON aj.id = d.jurisdiction_id
        WHERE ar.request_ref LIKE 'AR-%'
        ORDER BY ar.requested_at""",
}


def load_frames(db: Session) -> dict[str, pd.DataFrame]:
    conn = db.connection()
    frames = {k: pd.read_sql(text(q), conn) for k, q in SQL.items()}
    today = pd.Timestamp(date.today())
    g = frames["gaps"]
    for col in ("identified_at", "due_date", "resolved_at"):
        g[col] = pd.to_datetime(g[col])
    g["is_open"] = g["status"].isin(["Open", "In Remediation"])
    g["overdue"] = g["is_open"] & (g["due_date"] < today)
    g["days_open"] = ((g["resolved_at"].fillna(today) - g["identified_at"]).dt.days).astype(int)
    frames["risk"]["as_of"] = pd.to_datetime(frames["risk"]["as_of"])
    t = frames["tasks"]
    t["due_date"] = pd.to_datetime(t["due_date"])
    t["overdue"] = (t["status"] != "Completed") & (t["due_date"] < today)
    return frames


def summarise(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    risk, gaps, ass, access = frames["risk"], frames["gaps"], frames["assessments"], frames["access"]
    latest_date = risk["as_of"].max()
    latest_risk = risk[risk["as_of"] == latest_date].sort_values("residual_score", ascending=False)

    open_gaps = gaps[gaps["is_open"]]
    gap_matrix = (open_gaps.pivot_table(index="jurisdiction", columns="severity", values="gap_ref", aggfunc="count", fill_value=0)
                  .reindex(columns=SEV_ORDER, fill_value=0))
    gap_matrix["Total"] = gap_matrix.sum(axis=1)
    gap_matrix["Overdue"] = open_gaps.groupby("jurisdiction")["overdue"].sum().reindex(gap_matrix.index).fillna(0).astype(int)

    latest_cycle = ass["cycle"].max()
    cur = ass[(ass["cycle"] == latest_cycle) & (ass["result"] != "Not Applicable")].drop_duplicates(["control", "jurisdiction"], keep="last")
    effectiveness = cur.pivot_table(index="control", columns="jurisdiction", values="pass_rate", aggfunc="last")

    cycle_eff = (ass[ass["result"] != "Not Applicable"].assign(effective=lambda d: d["result"].eq("Effective"))
                 .groupby("cycle")["effective"].mean().mul(100).round(1).rename("pct_effective").reset_index())

    decisions = access.pivot_table(index="asset_jurisdiction", columns="decision", values="request_ref", aggfunc="count", fill_value=0)
    decisions["Total"] = decisions.sum(axis=1)
    if "DENIED" in decisions:
        decisions["Denial %"] = (decisions["DENIED"] / decisions["Total"] * 100).round(1)

    closed = gaps[gaps["status"] == "Resolved"]
    mttr = closed.groupby("severity")["days_open"].mean().reindex(SEV_ORDER).round(1).rename("mean_days_to_remediate").reset_index()

    return {"latest_risk": latest_risk, "gap_matrix": gap_matrix.reset_index(), "effectiveness": effectiveness,
            "cycle_effectiveness": cycle_eff, "decisions": decisions.reset_index(), "mttr": mttr,
            "open_gaps": open_gaps.assign(_rank=open_gaps["severity"].map({k: i for i, k in enumerate(SEV_ORDER)}))
                                  .sort_values(["_rank", "due_date"]).drop(columns="_rank")}


def excel_report(db: Session) -> bytes:
    frames = load_frames(db)
    sm = summarise(frames)
    kpis = pd.DataFrame([
        ("Report generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ("Jurisdictions assessed", len(sm["latest_risk"])),
        ("Average residual risk (0-100)", round(sm["latest_risk"]["residual_score"].mean(), 1)),
        ("Open compliance gaps", int(frames["gaps"]["is_open"].sum())),
        ("Open Critical/High gaps", int(frames["gaps"][frames["gaps"]["is_open"] & frames["gaps"]["severity"].isin(["Critical", "High"])].shape[0])),
        ("Overdue remediation", int(frames["gaps"]["overdue"].sum())),
        ("Control assessments on record", len(frames["assessments"])),
        ("Access requests evaluated", len(frames["access"])),
        ("Data", "SYNTHETIC portfolio data, not real institution data"),
    ], columns=["Metric", "Value"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        kpis.to_excel(xw, sheet_name="Summary", index=False)
        sm["latest_risk"].assign(as_of=lambda d: d["as_of"].dt.date).to_excel(xw, sheet_name="Jurisdiction Risk", index=False)
        sm["gap_matrix"].to_excel(xw, sheet_name="Gap Matrix", index=False)
        sm["open_gaps"].drop(columns=["is_open"]).assign(identified_at=lambda d: d["identified_at"].dt.strftime("%Y-%m-%d"),
                                                         due_date=lambda d: d["due_date"].dt.date, resolved_at=lambda d: d["resolved_at"].astype(str)
                                                         ).to_excel(xw, sheet_name="Open Gaps", index=False)
        sm["effectiveness"].to_excel(xw, sheet_name="Control Effectiveness")
        sm["cycle_effectiveness"].to_excel(xw, sheet_name="Effectiveness Trend", index=False)
        frames["tasks"].assign(due_date=lambda d: d["due_date"].dt.date).to_excel(xw, sheet_name="Remediation", index=False)
        sm["decisions"].to_excel(xw, sheet_name="Access Decisions", index=False)
        sm["mttr"].to_excel(xw, sheet_name="Time to Remediate", index=False)
        frames["risk"].assign(as_of=lambda d: d["as_of"].dt.date).to_excel(xw, sheet_name="Risk History", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(60, max(10, width + 2))
            ws.freeze_panes = "A2"
    return buf.getvalue()


def gaps_csv(db: Session) -> str:
    g = load_frames(db)["gaps"]
    return g.drop(columns=["is_open"]).to_csv(index=False)


def html_report(db: Session) -> str:
    frames = load_frames(db)
    sm = summarise(frames)
    lr = sm["latest_risk"]
    layout = dict(template="plotly_white", font=dict(family="Inter, Segoe UI, sans-serif", size=12), margin=dict(l=40, r=20, t=50, b=40))

    rating_colors = {"Critical": SEV_COLORS["Critical"], "High": SEV_COLORS["High"], "Medium": SEV_COLORS["Medium"], "Low": SEV_COLORS["Low"]}
    f1 = px.bar(lr, x="jurisdiction", y="residual_score", color="rating", color_discrete_map=rating_colors,
                category_orders={"rating": SEV_ORDER}, title="Residual risk by jurisdiction (0-100)", hover_data=["name", "control_effectiveness"])
    f1.update_layout(**layout, yaxis_range=[0, 100])

    f2 = px.line(frames["risk"], x="as_of", y="residual_score", color="jurisdiction", markers=True, title="Residual risk trend by quarter")
    f2.update_layout(**layout)

    eff = sm["effectiveness"]
    f3 = go.Figure(go.Heatmap(z=eff.values, x=list(eff.columns), y=list(eff.index), colorscale=[[0, "#0e3d7e"], [0.5, "#6aabf1"], [1, "#e8f2fd"]],
                              zmin=0, zmax=100, colorbar=dict(title="Pass %"), hovertemplate="%{y} / %{x}: %{z}%<extra></extra>"))
    f3.update_layout(**layout, title="Control pass rate, latest cycle (lower = darker = worse)", height=520)

    gm = sm["gap_matrix"]
    f4 = go.Figure([go.Bar(name=s, x=gm["jurisdiction"], y=gm[s], marker_color=SEV_COLORS[s]) for s in SEV_ORDER])
    f4.update_layout(**layout, barmode="stack", title="Open compliance gaps by jurisdiction and severity")

    def table(df: pd.DataFrame) -> str:
        return df.to_html(index=False, classes="tbl", border=0, na_rep="")

    top = sm["open_gaps"].head(25)[["gap_ref", "jurisdiction", "severity", "status", "title", "owner", "due_date", "overdue"]].assign(
        due_date=lambda d: d["due_date"].dt.date)
    figs = "".join(f.to_html(full_html=False, include_plotlyjs=False) for f in (f1, f2, f3, f4))
    kp = {
        "Average residual risk": f"{lr['residual_score'].mean():.1f}",
        "Open gaps": int(frames["gaps"]["is_open"].sum()),
        "Overdue": int(frames["gaps"]["overdue"].sum()),
        "Controls effective (latest)": f"{sm['cycle_effectiveness']['pct_effective'].iloc[-1]:.0f}%",
    }
    cards = "".join(f"<div class='card'><div class='v'>{v}</div><div class='k'>{k}</div></div>" for k, v in kp.items())
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>EMEA Guard - Executive Risk Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:Inter,'Segoe UI',sans-serif;margin:32px;color:#191919;background:#f9f9f9}}h1{{margin:0}}h2{{margin-top:36px}}
.sub{{color:#666}}.cards{{display:flex;gap:16px;margin:24px 0}}.card{{background:#fff;border:1px solid #e7e7e7;border-radius:8px;padding:16px 20px;flex:1}}
.v{{font-size:28px;font-weight:600}}.k{{color:#666;font-size:13px}}.panel{{background:#fff;border:1px solid #e7e7e7;border-radius:8px;padding:12px;margin:16px 0}}
.tbl{{border-collapse:collapse;width:100%;font-size:12px;background:#fff}}.tbl th,.tbl td{{padding:6px 8px;border-bottom:1px solid #e7e7e7;text-align:left}}
.tbl th{{background:#f3f4f6}}.note{{font-size:12px;color:#666;margin-top:32px}}</style></head><body>
<h1>EMEA Guard &mdash; Executive Data Governance Risk Report</h1>
<div class="sub">Generated {datetime.utcnow():%d %b %Y %H:%M} UTC &middot; Risk as of {lr['as_of'].max():%d %b %Y}</div>
<div class="cards">{cards}</div>
<div class="panel">{figs}</div>
<h2>Jurisdiction risk</h2>{table(lr[['jurisdiction','name','residual_score','rating','control_effectiveness','open_gap_score','overdue_ratio','access_denial_rate']])}
<h2>Open gaps by severity</h2>{table(sm['gap_matrix'])}
<h2>Mean days to remediate (resolved gaps)</h2>{table(sm['mttr'])}
<h2>Top open gaps</h2>{table(top)}
<p class="note">All figures are generated by EMEA Guard over SYNTHETIC data for portfolio demonstration. Not real institution data or a statement of regulatory compliance.</p>
</body></html>"""
