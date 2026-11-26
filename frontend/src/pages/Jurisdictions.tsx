import { useState } from "react";
import { api, DEMO, getSession } from "../api";
import { Card, DataTable, ErrorBox, Flag, Loading, PageHead, Status, toast, useApi } from "../components/ui";
import type { Jurisdiction, Requirement } from "../types";

const BLANK = { code: "", name: "", region: "Middle East", data_protection_authority: "", financial_regulator: "", primary_law: "", residency_regime: "Conditional", dpo_name: "", req_title: "", req_ref: "" };

export default function Jurisdictions() {
  const jurs = useApi<Jurisdiction[]>("/api/jurisdictions");
  const reqs = useApi<Requirement[]>("/api/requirements");
  const [sel, setSel] = useState<string>("IE");
  const [cat, setCat] = useState("");
  const [form, setForm] = useState(BLANK);
  const isAdmin = getSession()?.role === "admin";
  if (jurs.error || reqs.error) return <ErrorBox error={(jurs.error || reqs.error)!} />;
  if (!jurs.data || !reqs.data) return <Loading />;
  const j = jurs.data.find((x) => x.code === sel) ?? jurs.data[0];
  const applicable = reqs.data.filter((r) => r.jurisdiction === j.code || r.scope === "GLOBAL" || (r.scope === "EU" && j.is_eu));
  const shown = applicable.filter((r) => !cat || r.category === cat);
  const cats = Array.from(new Set(reqs.data.map((r) => r.category))).sort();

  const onboard = async () => {
    try {
      await api.post("/api/jurisdictions", {
        code: form.code, name: form.name, region: form.region, data_protection_authority: form.data_protection_authority,
        financial_regulator: form.financial_regulator, primary_law: form.primary_law, residency_regime: form.residency_regime,
        dpo_name: form.dpo_name || null,
        requirements: form.req_title ? [{ code: `${form.code}-01`, regime: form.primary_law, reference: form.req_ref || "TBC", title: form.req_title, description: form.req_title, category: "Data Localisation" }] : [],
      });
      toast(`${form.name} created in Onboarding status`);
      setForm(BLANK); jurs.reload(); reqs.reload();
    } catch (e: any) { toast(e.message, true); }
  };
  const activate = async (code: string) => {
    try { await api.post(`/api/jurisdictions/${code}/activate`); toast(`${code} activated`); jurs.reload(); } catch (e: any) { toast(e.message, true); }
  };

  return (
    <>
      <PageHead title="Jurisdiction management" desc={`${jurs.data.filter((x) => x.status === "Active").length} active EMEA jurisdictions and ${reqs.data.length} regulatory requirements (EU-wide, global and national), each mapped to rules, controls and policies.`} />
      <Card title="Jurisdictions">
        <DataTable rows={jurs.data} onRow={(r) => setSel(r.code)} selectedId={j.id} cols={[
          { key: "code", label: "Code", render: (r) => <b>{r.code}</b> },
          { key: "name", label: "Jurisdiction" }, { key: "region", label: "Region" },
          { key: "is_eu", label: "EU / EEA", render: (r) => (r.is_eu ? "EU" : r.is_eea ? "EEA" : r.eu_adequacy ? "EU adequacy" : "Third country") },
          { key: "primary_law", label: "Primary framework" },
          { key: "residency_regime", label: "Residency", render: (r) => <span className={`badge ${r.residency_regime === "Strict" ? "b-bad" : r.residency_regime === "Conditional" ? "b-warn" : "b-good"}`}>{r.residency_regime}</span> },
          { key: "banking_secrecy", label: "Banking secrecy", render: (r) => (r.banking_secrecy ? "Yes" : "—") },
          { key: "national_requirements", label: "National reqs", num: true },
          { key: "data_assets", label: "Assets", num: true }, { key: "employees", label: "Staff", num: true },
          { key: "inherent_risk", label: "Inherent risk ×", num: true },
          { key: "status", label: "Status", render: (r) => <>{<Status s={r.status} />}{r.status === "Onboarding" && isAdmin && <button className="ghost" onClick={(e) => { e.stopPropagation(); activate(r.code); }}>Activate</button>}</> },
        ]} />
      </Card>

      <div className="grid mt" style={{ gridTemplateColumns: "1fr 360px", alignItems: "start" }}>
        <Card title={`Requirements applicable in ${j.name}`} sub={`${applicable.length} requirements`} right={<select value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</select>}>
          <dl className="kv" style={{ marginBottom: 12 }}>
            <dt>Data protection authority</dt><dd>{j.data_protection_authority}</dd>
            <dt>Financial regulator</dt><dd>{j.financial_regulator}</dd>
            <dt>EU adequacy / EEA</dt><dd><Flag on={j.is_eea || j.eu_adequacy} yes={j.is_eea ? "EEA member" : "EU adequacy decision"} no="Third country: transfers need safeguards" /></dd>
          </dl>
          <DataTable rows={shown} cols={[
            { key: "code", label: "Code", render: (r) => <span className="mono">{r.code}</span> },
            { key: "regime", label: "Regime", render: (r) => <>{r.regime}<div className="faint">{r.reference}</div></> },
            { key: "title", label: "Requirement", render: (r) => <>{r.title}<div className="faint">{r.description}</div></> },
            { key: "category", label: "Category" },
            { key: "scope", label: "Scope" },
            { key: "min_classification", label: "Applies from", render: (r) => ["", "Public", "Internal", "Confidential", "Restricted"][r.min_classification] },
          ]} />
        </Card>
        <Card title="Onboard a jurisdiction" sub="requirements workflow">
          <div className="grid" style={{ gap: 8 }}>
            <p className="faint" style={{ margin: 0 }}>New jurisdictions start in <b>Onboarding</b>. Activation is blocked until readiness checks pass: requirements captured, DPO assigned, regulators recorded, residency regime set.</p>
            {(["code", "name", "data_protection_authority", "financial_regulator", "primary_law", "dpo_name", "req_title", "req_ref"] as const).map((k) => (
              <label key={k} className="field">{{ code: "ISO code (2 letters)", name: "Name", data_protection_authority: "Data protection authority", financial_regulator: "Financial regulator", primary_law: "Primary law", dpo_name: "DPO name", req_title: "First requirement", req_ref: "Requirement reference" }[k]}
                <input value={form[k]} maxLength={k === "code" ? 2 : undefined} onChange={(e) => setForm({ ...form, [k]: k === "code" ? e.target.value.toUpperCase() : e.target.value })} /></label>
            ))}
            <label className="field">Region<select value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}>{["Europe", "Middle East", "Africa"].map((r) => <option key={r}>{r}</option>)}</select></label>
            <label className="field">Residency regime<select value={form.residency_regime} onChange={(e) => setForm({ ...form, residency_regime: e.target.value })}>{["Open", "Conditional", "Strict"].map((r) => <option key={r}>{r}</option>)}</select></label>
            <button className="primary" disabled={!isAdmin || DEMO || form.code.length !== 2 || !form.name} onClick={onboard}>Start onboarding</button>
            {DEMO ? <div className="faint">Onboarding writes to PostgreSQL, so it is available in the full-stack deployment only.</div> : !isAdmin && <div className="faint">Admin role required.</div>}
          </div>
        </Card>
      </div>
    </>
  );
}
