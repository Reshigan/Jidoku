/* What the panels added this session actually render.
   The endpoint-coverage walk proves each one's request is made; it proves nothing about what
   comes back onto the screen. These assert the content, because a panel that fetches correctly
   and renders an empty table is a panel nobody would notice was broken. */
import { expect, test, type Page } from "@playwright/test";

const ROLES = ["builder", "reviewer", "approver", "auditor"];
const IR = [{
  object: "PicklistOption", product: "SuccessFactors", system_binding: "KOM-SF-DEV",
  // Tier B, because the SuccessFactors adapter says so: an option is a child of the PickListV2
  // payload, not a write target of its own (ADR-0045). Declaring A here was refused at load, which
  // is the gate working — the fixture was the thing that was wrong.
  external_code: "MIBCO_FLAG", tier: "B",
  source: { workbook: "ZA-payroll-v3.xlsx", signed_by: "T. Mabaso", date: "2026-09-01" },
  intent: {
    externalCode: "MIBCO_FLAG",
    entitlement: { value: 21, refinement: { kind: "bounded", max: 15, statute: "BCEA s20",
                                            signed_by: "T. Mabaso", date: "2026-09-01" } },
  },
  contract: { owner: "EC", consumers: ["Time Off", "EE Reporting"], feeds: ["ECC IT0001"],
              statutory: "MIBCO main agreement" },
}];

/* These run against one API process and one store, alongside every other spec. Returning the
   engagement id — rather than reading whatever the selector happens to hold later — is what keeps
   a test from loading its intent into somebody else's engagement when two workers overlap. */
async function open(page: Page, who: string): Promise<string> {
  await page.goto("/");
  await page.getByLabel("Name").fill(who);
  for (const r of ROLES) {
    const btn = page.getByRole("button", { name: r, exact: true });
    if (!((await btn.getAttribute("class"))?.includes("primary") ?? false)) await btn.click();
  }
  await page.getByRole("button", { name: "Enter the console" }).click();
  await expect(page.locator(".topbar")).toContainText(who);
  await page.getByRole("button", { name: "New engagement" }).click();
  await page.getByLabel("Client").fill("Komatsu");
  const name = `Panels ${who} ${Date.now()}`;
  await page.getByLabel("Name").last().fill(name);
  await page.getByRole("button", { name: "Open it" }).click();
  await expect(page.locator(".scrim")).toHaveCount(0);
  // Opening selects it. Assert that before reading the id, so an overlapping worker moving the
  // selection fails here rather than quietly redirecting the rest of the test.
  await expect(page.locator(".head h1")).toHaveText(name);
  return page.getByLabel("Engagement").inputValue();
}

test("the type-check prints the statute, the signer and the date it was refused on", async ({ page, request }) => {
  const eid = await open(page, "panel.tester");
  expect((await request.post(`/engagements/${eid}/ir`, { data: IR })).ok()).toBeTruthy();

  await page.getByRole("tab", { name: /^Intent/ }).click();
  const types = page.locator(".sec", { hasText: "What the types say" });
  // The rejection is the auditor's control narrative, so the screen must show it word for word.
  await expect(types).toContainText("configured as 21");
  await expect(types).toContainText("signed statutory maximum is 15");
  await expect(types).toContainText("BCEA s20, signed by T. Mabaso on 2026-09-01");
  await expect(types).toContainText("not a configuration choice");
});

test("the contract registry names the owner and everyone registered to read it", async ({ page, request }) => {
  const eid = await open(page, "contract.tester");
  await request.post(`/engagements/${eid}/ir`, { data: IR });

  await page.getByRole("tab", { name: /^Intent/ }).click();
  const row = page.locator(".sec", { hasText: "Cross-module contracts" }).locator("tbody tr").first();
  await expect(row).toContainText("EC");
  await expect(row).toContainText("Time Off");
  await expect(row).toContainText("EE Reporting");
  await expect(row).toContainText("MIBCO main agreement");
});

test("the account of itself says what it cannot measure, not only what it can", async ({ page }) => {
  await open(page, "account.tester");
  await page.getByRole("tab", { name: /^Evidence/ }).click();
  const panel = page.locator(".sec", { hasText: "What I got wrong" });
  await expect(panel).toContainText("I have refused nothing here");
  await panel.getByText("What these numbers cannot tell you").click();
  await expect(panel).toContainText("never reached a gate");
  await expect(panel).toContainText("Harm avoided");
});

test("the portfolio says which engagements need a person, in words", async ({ page }) => {
  await open(page, "portfolio.tester");
  await page.getByRole("tab", { name: /^Portfolio/ }).click();
  const panel = page.locator(".sec", { hasText: "Every engagement" });
  await expect(panel).toContainText("need a person today");
  // A night that has never run is on the list, not assumed fine — the failure this exists for is
  // a programme nobody has opened in three weeks looking exactly like one that is going well.
  await expect(panel.locator("tbody tr").first()).toContainText("No night has ever been worked");
});

test("the night shift card reports a stopped clock above the handover", async ({ page }) => {
  await open(page, "clock.tester");
  await page.getByRole("tab", { name: /^Crew/ }).click();
  const panel = page.locator(".sec", { hasText: "The night shift" });
  await expect(panel).toContainText("No night has ever been worked here");
});

/* The programme screen. Two things are worth an end-to-end test here and they are both absences:
   the screen must not invent an empty programme when none was absorbed, and it must not publish a
   percentage complete. Both are easy to add later by accident and neither shows up in a unit test
   of the API. */
const PLAN = {
  conditions: [{ what: "DEV and QAL provisioned", by: "1 Oct",
                 consequence: "Week 1 cannot start; day-for-day slip" }],
  gates: [{ gate_id: "G1", name: "Baseline accepted", date: "Fri 9 Oct", due_on: "2026-10-09",
            criteria: "extract accepted", evidence: "baseline manifest", approver: "Lead" },
          { gate_id: "G3", name: "Hypercare entry", date: "week 8", due_on: "",
            criteria: "support model accepted", evidence: "signed RACI", approver: "IT owner" }],
  tasks: [{ task_id: "T-001", task: "Access check", week: "B1", owner: "PM", gate: "G1",
            declared_status: "Complete" }],
};

test("a programme nobody absorbed is not shown as a programme with nothing in it", async ({ page }) => {
  await open(page, "prog.empty");
  await page.getByRole("tab", { name: /^Programme/ }).click();
  await expect(page.locator(".empty")).toContainText("No plan has been absorbed");
  await expect(page.locator(".empty")).toContainText("jidoka-absorb.py");
});

test("the programme shows the register's claim beside the chain's answer, and no percentage", async ({ page, request }) => {
  const eid = await open(page, "prog.tester");
  expect((await request.post(`/engagements/${eid}/programme`, { data: PLAN })).ok()).toBeTruthy();

  await page.getByRole("tab", { name: /^Programme/ }).click();

  /* Anchored on each section's own note rather than its title: the summary section's sentence
     names the other three, so a title match resolves to two sections and the assertion is
     ambiguous about which one it read. */
  const conds = page.locator(".sec", { hasText: "Silence is shown as silence" });
  await expect(conds).toContainText("nobody has said");
  await expect(conds).toContainText("day-for-day slip");

  // A gate whose date did not resolve to a day says so, and is not called late.
  const gates = page.locator(".sec", { hasText: "A gate passes on evidence, by somebody" });
  await expect(gates).toContainText("(not a day)");
  await expect(gates).not.toContainText("late");

  // The register says "Complete"; the chain cannot see the task. Both are on the row.
  const row = page.locator(".sec", { hasText: "kept apart from what the register claims" })
    .locator("tbody tr").first();
  await expect(row).toContainText("Complete");
  await expect(row).toContainText("cannot see it");

  /* No percentage anywhere, and the screen says why rather than leaving the absence to be read as
     an oversight. Asserted on the character, not on the word "progress" — which the sentence
     explaining the absence necessarily contains. */
  await expect(page.locator("main")).not.toContainText("%");
  await expect(page.locator("main")).toContainText("No percentage is published");
  await expect(page.locator("main .bar, main progress, main meter")).toHaveCount(0);
});


/* The specification screen's one job is the column that says the platform cannot answer. */
test("an untraced requirement is shown first and is never counted as covered", async ({ page, request }) => {
  const eid = await open(page, "spec.tester");
  expect((await request.post(`/engagements/${eid}/specification`, {
    data: {
      requirements: [
        { req_id: "BRS-EC-001", requirement: "Single instance", rationale: "r", fit: "STD",
          control: "C01" },
        { req_id: "BRS-TIM-001", requirement: "Leave accrual by country", rationale: "statute",
          fit: "GAP", control: "C02" }],
      controls: [{ control_id: "C01", objective: "Every change is attributable", owner: "GONXT",
                   frequency: "per cycle", evidence: "the change log" }],
    },
  })).ok()).toBeTruthy();

  await page.getByRole("tab", { name: /^Specification/ }).click();
  const head = page.locator(".sec", { hasText: "Each requirement against the objects" });
  await expect(head).toContainText("0 of 2 requirements are described by signed intent");
  await expect(head).toContainText("name no configuration object at all");
  await expect(head).toContainText("declared 1 of these a GAP");

  const table = page.locator(".sec", { hasText: "Worst first" });
  await expect(table.locator("tbody tr").first()).toContainText("cannot tell");

  // C02 is cited and never defined, so the requirements it assures are unassured.
  await expect(page.locator(".sec", { hasText: "What each control assures" }))
    .toContainText("which this specification does not define");

  await expect(page.locator("main")).not.toContainText("%");
});


/* The proposals screen's one job is to show a person what they are signing, and to make clear that
   the drafter did not. */
const DRAFT = {
  object: "FOCostCenter", product: "SuccessFactors", system_binding: "KOM-SF-DEV", tier: "A",
  external_code: "CC1", intent: { externalCode: "CC1", name: "Finance" },
  source: { workbook: "SDD §5.1", signed_by: "", date: "" },
};

test("an engagement nobody drafted for says so rather than showing an empty table", async ({ page }) => {
  await open(page, "prop.empty");
  await page.getByRole("tab", { name: /^Proposals/ }).click();
  await expect(page.locator(".empty")).toContainText("No agent has drafted anything");
});

test("a draft shows where its values came from and who drafted it, and signing records the signer", async ({ page, request }) => {
  const eid = await open(page, "prop.signer");
  expect((await request.post(`/engagements/${eid}/proposals`, { data: { records: [DRAFT] } })).ok())
    .toBeTruthy();

  await page.getByRole("tab", { name: /^Proposals/ }).click();
  const waiting = page.locator(".sec", { hasText: "Drafts an agent authored" });
  await expect(waiting).toContainText("SuccessFactors:FOCostCenter:CC1");
  await expect(waiting).toContainText("SDD §5.1");
  await expect(waiting).toContainText("anonymous");          // the drafter, named

  await waiting.getByRole("button", { name: "Sign", exact: true }).click();
  const answered = page.locator(".sec", { hasText: "What was signed and what was declined" });
  await expect(answered).toContainText("prop.signer");       // the console's identity, not a typed name
  await expect(answered).toContainText("signed");
});

test("a drafter cannot sign its own draft, and the refusal says why", async ({ page }) => {
  const eid = await open(page, "prop.self");     // signed in as prop.self, the drafter below
  // The console user drafts through the API under their own identity, then tries to sign in the UI.
  // The token is minted the way the console mints it (POST /auth/token) rather than read out of
  // sessionStorage, which a browser may deny — the console guards for that and keeps the session in
  // memory, so there is nothing to read. A missing token fails the test rather than skipping it: a
  // skip would be a test that passes by not running, on the one rule this screen exists to show.
  const minted = await page.request.post("/auth/token", {
    data: { subject: "prop.self", roles: ["builder", "reviewer", "approver", "auditor"] },
  });
  expect(minted.ok()).toBeTruthy();
  const token = (await minted.json()).token as string;
  const res = await page.request.post(`/engagements/${eid}/proposals`, {
    data: { records: [DRAFT] }, headers: { authorization: `Bearer ${token}` },
  });
  expect(res.ok()).toBeTruthy();
  await page.getByRole("tab", { name: /^Proposals/ }).click();
  await page.getByRole("button", { name: "Sign", exact: true }).click();
  await expect(page.locator(".modal.refusal")).toContainText("may not sign it");
});
