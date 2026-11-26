/**
 * Parity test: the TypeScript demo engine must reproduce every decision the Python engine
 * made in the exported fixture (decision, risk score, failed rules and applicable rules).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildContext, evaluate } from "./engine";

const dir = resolve(__dirname, "../../public/demo/api");
const load = (n: string) => JSON.parse(readFileSync(resolve(dir, `${n}.json`), "utf-8"));

describe("demo engine parity with the Python control engine", () => {
  const data = {
    roles: load("roles"), requirements: load("requirements"), jurisdictions: load("jurisdictions"),
    adequacy: load("adequacy"), mechanisms: load("transfer-mechanisms"), rules: load("rules"),
  };
  const employees = new Map(load("employees").map((e: any) => [e.id, e]));
  const assets = new Map(load("assets").map((a: any) => [a.id, a]));
  const cases = load("parity-cases");

  it("has a meaningful number of cases", () => expect(cases.length).toBeGreaterThanOrEqual(300));

  it("matches every Python decision", () => {
    const mismatches: string[] = [];
    for (const c of cases) {
      const ctx = buildContext(data, employees.get(c.employee_id) as any, assets.get(c.asset_id) as any,
        { access_type: c.access_type, purpose: c.purpose, ticket_ref: c.ticket_ref }, c.approvals, c.as_of);
      const t = evaluate(ctx, data.rules);
      const failed = t.rules.filter((r) => !r.passed).map((r) => r.code).sort();
      const applicable = t.rules.filter((r) => r.applicable).map((r) => r.code).sort();
      if (t.decision !== c.expected.decision || t.risk_score !== c.expected.risk_score ||
          JSON.stringify(failed) !== JSON.stringify(c.expected.failed) || JSON.stringify(applicable) !== JSON.stringify(c.expected.applicable)) {
        mismatches.push(`${c.employee_id}/${c.asset_id}/${c.access_type}: ts=${t.decision},${t.risk_score},${failed} py=${c.expected.decision},${c.expected.risk_score},${c.expected.failed}`);
      }
    }
    expect(mismatches).toEqual([]);
  });
});
