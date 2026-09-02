import { expect, test } from "@playwright/test";

/**
 * "Every capability is reachable from the frontend" is a claim worth failing a build over.
 * This walks the console, records every request it actually makes, and compares that against
 * the API's own OpenAPI document. A new endpoint with no UI path fails here.
 */
const OUT_OF_BAND = new Set([
  "POST /engagements/{eid}/plan", // the console reads the plan; it never ledgers a rebuild by hand
]);

test("the console reaches every endpoint the API publishes", async ({ page, request }) => {
  const spec = await (await request.get("/openapi.json")).json() as {
    paths: Record<string, Record<string, unknown>>;
  };
  const published = new Set<string>();
  for (const [path, methods] of Object.entries(spec.paths)) {
    for (const m of Object.keys(methods)) published.add(`${m.toUpperCase()} ${path}`);
  }

  const seen = new Set<string>();
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.origin !== new URL(page.url() || "http://x").origin && !u.pathname.startsWith("/")) return;
    seen.add(`${r.method()} ${templated(u.pathname)}`);
  });

  await page.goto("/");
  await page.getByLabel("Name").fill("coverage.tester");
  // Role buttons are toggles and "builder" is pre-picked; clicking the others must not drop it,
  // or this tester loses register_system, execute and arm.
  for (const r of ["reviewer", "approver", "auditor"]) {
    const btn = page.getByRole("button", { name: r, exact: true });
    if (!((await btn.getAttribute("class")) || "").includes("primary")) await btn.click();
  }
  await page.getByRole("button", { name: "Enter the console" }).click();

  await page.getByRole("button", { name: "New engagement" }).click();
  await page.getByLabel("Client").fill("Komatsu");
  await page.getByLabel("Name").fill(`Coverage ${Date.now()}`);
  await page.getByRole("button", { name: "Open it" }).click();

  // Landscape
  await page.getByRole("tab", { name: /^Landscape/ }).click();
  await page.getByRole("button", { name: "Register a system" }).click();
  await page.getByLabel("System id").fill("KOM-SF-DEV");
  await page.getByLabel("Product").fill("SuccessFactors");
  await page.getByLabel("Role").selectOption("TARGET");
  await page.getByLabel("Environment").selectOption("DEV");
  await page.getByRole("checkbox").check();   // a target with no write credentials can never be bound
  await page.getByRole("button", { name: "Register", exact: true }).click();

  // An ABAP pair, so the walk has a step whose completion runs through a transport (ADR-0006).
  for (const [sid, env, promotes] of [["KOM-S4-PRD", "PROD", ""], ["KOM-S4-DEV", "DEV", "KOM-S4-PRD"]]) {
    await page.getByRole("button", { name: "Register a system" }).click();
    await page.getByLabel("System id").fill(sid);
    await page.getByLabel("Product").fill("S4HANA");
    await page.getByLabel("Role").selectOption("TARGET");
    await page.getByLabel("Environment").selectOption(env);
    await page.getByLabel("Promotes into").fill(promotes);
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Register", exact: true }).click();
    await dismissScrim(page);
  }

  // Intent: check then load
  await page.getByRole("tab", { name: /^Intent/ }).click();
  await page.getByRole("button", { name: "Load intent" }).click();
  const records = JSON.stringify([{
    object: "PayComponent", product: "SuccessFactors", system_binding: "KOM-SF-DEV", tier: "A",
    intent: { code: "BASIC" }, source: { workbook: "w.xlsx", signed_by: "x", date: "2026-01-01" },
  }, {
    object: "A_CostCenter", product: "S4HANA", system_binding: "KOM-S4-DEV", tier: "A",
    intent: { CostCenter: "CC90", CompanyCode: "1000" },
    source: { workbook: "w.xlsx", signed_by: "x", date: "2026-01-01" },
  }]);
  await page.getByLabel("Records (JSON array)").fill(records);
  await page.getByRole("button", { name: "Check it" }).click();
  await page.getByRole("button", { name: "Load it" }).click();

  // Decisions: raise and resolve
  await page.getByRole("tab", { name: /^Decisions/ }).click();
  await page.getByRole("button", { name: "Raise a decision" }).click();
  await page.getByLabel("Reference").fill("DP-COV");
  await page.getByLabel("Kind").selectOption("DESIGN");
  await page.getByLabel("Question").fill("Which grouping?");
  await page.getByLabel("Owner").fill("Komatsu HR");
  await page.getByRole("button", { name: "Raise it" }).click();
  await page.locator(".station", { hasText: "DP-COV" })
    .getByRole("button", { name: "Take this decision" }).click();
  await page.getByRole("textbox", { name: /^Decision/ }).fill("By legal entity");
  await page.getByRole("button", { name: "Record the decision" }).click();

  // Work: a full run, then an approval attempt (refused — same person executed it)
  await page.getByRole("tab", { name: /^Work/ }).click();
  await page.getByRole("button", { name: "Take before-snapshot" }).first().click();
  await page.getByRole("button", { name: "Execute", exact: true }).first().click();
  await page.getByRole("button", { name: "Validate" }).first().click();
  await page.getByRole("button", { name: "Approve", exact: true }).first().click();
  await page.getByRole("button", { name: "Understood" }).click();

  // Configure: bind a connector, rehearse, snapshot, then arm and disarm the target.
  // This tester holds every role, so an armed live write is correctly refused (a builder may not
  // spend its own arming) — the point here is that each endpoint has a path, not the SoD split,
  // which services/api/tests owns.
  await page.getByRole("tab", { name: /^Configure/ }).click();
  await page.getByRole("button", { name: "Bind connector" }).first().click();
  await dismissScrim(page);
  await page.getByRole("button", { name: "Snapshot" }).first().click();
  await dismissScrim(page);
  await page.getByRole("button", { name: /^(Dry run|Write for real)$/ }).first().click();
  await dismissScrim(page);
  await page.getByRole("button", { name: "Arm for live" }).first().click();
  await dismissScrim(page);
  await page.getByRole("button", { name: "Disarm" }).first().click();
  await dismissScrim(page);
  // A snapshot exists, so a rollback is offered — and refused, because this tester armed nothing.
  await page.getByRole("button", { name: "Roll back" }).first().click();
  await dismissScrim(page);
  // The ABAP step offers its next hop. Refused here too (no transport was ever created), which is
  // the gate firing, not a break: what this spec asserts is that the path exists.
  await page.getByRole("button", { name: /^(Advance transport|Move to )/ }).first().click();
  await dismissScrim(page);

  // Memory: form a belief, re-check it, correct it, and offer it for promotion (ADR-0010).
  await page.getByRole("tab", { name: /^Memory/ }).click();
  await page.getByRole("button", { name: "Record a belief" }).click();
  await page.getByLabel("Subject").fill("cost-centres");
  await page.getByLabel(/^What we believe required/).fill("Cost centres are mastered upstream and replicated read-only");
  await page.getByLabel("Read from").fill("design:CO-01");
  await page.getByLabel("The source as it read").fill("mastered upstream, replicated read-only");
  await page.getByRole("button", { name: "Record it" }).click();
  await dismissScrim(page);

  await page.getByRole("button", { name: "Re-check it" }).first().click();
  await dismissScrim(page);

  // As-of: what was believed on a given day, answered from the validity intervals.
  await page.getByLabel("As of date").fill(new Date().toISOString().slice(0, 10));
  await page.getByRole("button", { name: "Read it back" }).click();
  await dismissScrim(page);
  const back = page.getByRole("button", { name: "Back to now" });
  if (await back.count()) await back.click();

  await page.getByRole("button", { name: "Correct it" }).first().click();
  await page.getByLabel("What we believe now").fill("Cost centres are mastered upstream; local edits are rejected");
  await page.getByLabel("Read from").fill("design:CO-01");
  await page.getByLabel("The source as it reads").fill("mastered upstream, local edits rejected");
  await page.getByRole("button", { name: "Replace it" }).click();
  await dismissScrim(page);

  // Promotion crosses the tenant boundary. Refused or accepted, the path is what is asserted here.
  await page.getByRole("button", { name: /^Promote to shared knowledge/ }).first().click();
  await page.getByLabel("Approved by").fill("q.approver");
  await page.getByRole("button", { name: "Approve the crossing" }).click();
  await dismissScrim(page);

  // Learn from a system: bind a reader (no write half) and harvest its own metadata (ADR-0012).
  await page.getByRole("button", { name: /^Learn from a system/ }).click();
  await page.getByLabel(/^System/).selectOption("KOM-SF-DEV");
  const bindReader = page.getByRole("button", { name: "Bind a read-only connector" });
  if (await bindReader.count()) await bindReader.click();
  const readIt = page.getByRole("button", { name: "Read it", exact: true });
  await expect(readIt).toBeEnabled();          // the reader binding lands before the read is offered
  await readIt.click();
  await dismissScrim(page);

  // Verify: read the live systems against signed intent, then govern a number range and draw
  // the next free code from it (ADR-0013, ADR-0014).
  await page.getByRole("tab", { name: /^Verify/ }).click();
  await page.getByRole("button", { name: /^(Run verification|Verify again)$/ }).click();
  await dismissScrim(page);
  await page.getByLabel("Range id").fill("TT-COV");
  await page.getByLabel("Object type").fill("TimeType");
  await page.getByLabel("Prefix").fill("TT_COV_");
  await page.getByRole("button", { name: "Register range" }).click();
  await dismissScrim(page);
  await page.getByRole("button", { name: "Allocate next" }).first().click();
  await dismissScrim(page);

  // Documents: the pack is projected from signed intent, so opening it is the whole path.
  await page.getByRole("tab", { name: /^Documents/ }).click();
  await expect(page.locator(".doc-tab").first()).toBeVisible();
  await page.locator(".doc-tab").nth(1).click();
  await dismissScrim(page);

  // Phase advance, ledger, evidence
  await page.getByRole("tab", { name: /^Line/ }).click();
  await page.getByRole("button", { name: /^Advance to/ }).first().click();
  await page.getByRole("tab", { name: /^Ledger/ }).click();
  await page.getByRole("tab", { name: /^Evidence/ }).click();
  await expect(page.getByText(/The chain verifies|The chain breaks/)).toBeVisible();

  const missing = [...published].filter((e) => !seen.has(e) && !OUT_OF_BAND.has(e)).sort();
  expect(missing, `endpoints with no path through the console:\n${missing.join("\n")}`).toEqual([]);
});

/** A refusal modal is a success here — it means the gate fired. Clear it and keep walking.
    Scrims stack: a refusal can open over a dialog that has its own scrim, so clear until none
    is left rather than assuming a single match. */
async function dismissScrim(page: import("@playwright/test").Page) {
  await page.waitForTimeout(500);
  for (let i = 0; i < 4 && await page.locator(".scrim").count(); i++) {
    await page.locator(".scrim").last().click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(300);
  }
}

/** Collapse concrete ids back to the OpenAPI template so the two sets are comparable. */
function templated(p: string): string {
  return p
    .replace(/^\/engagements\/[^/]+\/decisions\/[^/]+\/resolve$/, "/engagements/{eid}/decisions/{dp_id}/resolve")
    .replace(/^\/engagements\/[^/]+\/execution\/arm\/[^/]+$/, "/engagements/{eid}/execution/arm/{system_id}")
    .replace(/^\/engagements\/[^/]+\/documents\/[^/]+$/, "/engagements/{eid}/documents/{document}")
    .replace(/^\/engagements\/[^/]+\/memory\/[^/]+\/(recheck|correct|promote)$/,
             (_m, act) => `/engagements/{eid}/memory/{claim_id}/${act}`)
    .replace(/^\/engagements\/[^/]+(\/.*)?$/, (_m, rest) => `/engagements/{eid}${rest ?? ""}`)
    .replace(/^\/engagements\/\{eid\}$/, "/engagements/{eid}");
}
