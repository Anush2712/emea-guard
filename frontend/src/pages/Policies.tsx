import { useState } from "react";
import { api, getSession } from "../api";
import { Card, DataTable, ErrorBox, fmtDate, Loading, PageHead, Status, toast, useApi } from "../components/ui";
import type { Policy } from "../types";

export default function Policies() {
  const pols = useApi<Policy[]>("/api/policies");
  const [selId, setSelId] = useState<number | null>(null);
  const [draft, setDraft] = useState({ change_summary: "", content: "", major: false });
  const role = getSession()?.role;
  if (pols.error) return <ErrorBox error={pols.error} />;
  if (!pols.data) return <Loading />;
  const p = pols.data.find((x) => x.id === selId) ?? pols.data[0];
  const current = p.versions.find((v) => v.version === p.current_version) ?? p.versions.at(-1);
  const update = (np: Policy) => pols.setData(pols.data!.map((x) => (x.id === np.id ? { ...x, ...np } : x)));

  const submitDraft = async () => {
    try { update(await api.post<Policy>(`/api/policies/${p.id}/versions`, { ...draft, content: draft.content || current?.content || "" }));
      setDraft({ change_summary: "", content: "", major: false }); toast("Draft submitted for review"); } catch (e: any) { toast(e.message, true); }
  };
  const approve = async (vid: number) => {
    try { update(await api.post<Policy>(`/api/policies/${p.id}/versions/${vid}/approve`)); toast("Version approved and published"); } catch (e: any) { toast(e.message, true); }
  };

  return (
    <>
      <PageHead title="Policy management" desc="Policies, standards and procedures with full version history, regulatory mapping, review cycles and a maker-checker approval workflow (an author cannot approve their own change)." />
      <Card title="Policy library">
        <DataTable rows={pols.data} onRow={(r) => setSelId(r.id)} selectedId={p.id} cols={[
          { key: "code", label: "Code", render: (r) => <span className="mono">{r.code}</span> },
          { key: "title", label: "Title" }, { key: "doc_type", label: "Type" }, { key: "owner", label: "Owner" },
          { key: "current_version", label: "Version", render: (r) => `v${r.current_version}` },
          { key: "version_count", label: "Versions", num: true },
          { key: "next_review_date", label: "Next review", render: (r) => <span style={{ color: r.review_overdue ? "#a3191a" : undefined }}>{fmtDate(r.next_review_date)}{r.review_overdue ? " · overdue" : ""}</span> },
          { key: "requirements", label: "Maps to", render: (r) => <span className="faint">{r.requirements.join(", ")}</span> },
        ]} />
      </Card>
      <div className="grid g2 mt">
        <Card title={`${p.code} · ${p.title}`} sub={`v${p.current_version} · review every ${p.review_cycle_months} months`}>
          <h3 style={{ marginBottom: 8 }}>Version history</h3>
          <div className="grid" style={{ gap: 8 }}>
            {[...p.versions].reverse().map((v) => (
              <div key={v.id} className="card" style={{ padding: 12 }}>
                <div className="row"><b>v{v.version}</b><Status s={v.status} /><span className="faint">{fmtDate(v.created_at)} · {v.author}{v.approved_by ? ` · approved by ${v.approved_by}` : ""}</span></div>
                <div style={{ marginTop: 4 }}>{v.change_summary}</div>
                {v.status === "In Review" && role === "admin" && <button className="primary" style={{ marginTop: 8 }} onClick={() => approve(v.id)}>Approve & publish</button>}
              </div>
            ))}
          </div>
          <h3 className="mt" style={{ marginBottom: 8 }}>Current text</h3>
          <pre className="doc">{current?.content}</pre>
        </Card>
        <Card title="Propose a change">
          {role === "auditor" ? <div className="faint">Auditors have read-only access.</div> : (
            <div className="grid" style={{ gap: 10 }}>
              <label className="field">Change summary<input value={draft.change_summary} placeholder="e.g. Add DORA Art. 28 register requirements" onChange={(e) => setDraft({ ...draft, change_summary: e.target.value })} /></label>
              <label className="field">Revised content (leave blank to start from the current text)<textarea rows={10} value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} /></label>
              <label className="check"><input type="checkbox" checked={draft.major} onChange={(e) => setDraft({ ...draft, major: e.target.checked })} />Major revision (v{Number(p.current_version.split(".")[0]) + 1}.0)</label>
              <button className="primary" disabled={!draft.change_summary} onClick={submitDraft}>Submit for review</button>
              <div className="faint">Drafts go to <b>In Review</b>. An admin who is not the author approves; the previous version is superseded and the review date resets. Every step is written to the audit trail.</div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
