import { expect, test, type Page } from "@playwright/test";
import { VIEWS } from "../src/ui";

/* These walk the console the way a person does: sign in, then reach every capability the
   platform exposes through the interface alone. No request is made behind the UI's back. */

const ROLES = ["builder", "reviewer", "approver", "auditor"];

async function signIn(page: Page, who: string, roles: string[] = ROLES) {
  await page.goto("/");
  await page.getByLabel("Name").fill(who);
  // "builder" starts selected; click only the roles whose current state is wrong.
  for (const r of ROLES) {
    const btn = page.getByRole("button", { name: r, exact: true });
    const selected = (await btn.getAttribute("class"))?.includes("primary") ?? false;
    if (selected !== roles.includes(r)) await btn.click();
  }
  await page.getByRole("button", { name: "Enter the console" }).click();
  await expect(page.locator(".topbar")).toContainText(who);
}

async function newEngagement(page: Page, client: string, name: string) {
  await page.getByRole("button", { name: "New engagement" }).click();
  await page.getByLabel("Client").fill(client);
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Open it" }).click();
  await expect(page.locator(".scrim")).toHaveCount(0);
  // Opening an engagement selects it.
  await expect(page.locator(".head h1")).toHaveText(name);
}

/** The tallest gap between a panel's body and the content in it, in pixels — for panels that did
 *  not ask to fill the glass. A board marked `data-fill="stretch"` claims the height on purpose
 *  (its panels *are* the screen), so a gap there is the design, not a fault. Everywhere else a gap
 *  means two panels both claimed the row's slack and only one could use it. */
async function slack(page: Page): Promise<number> {
  return page.locator(".board:not([data-fill]) > .sec").evaluateAll((els) =>
    Math.max(0, ...els.map((el) => {
      const body = [...el.children].find((c) => !c.classList.contains("sec-head"));
      if (!body) return 0;
      const used = [...body.children].reduce((h, c) => h + c.getBoundingClientRect().height, 0);
      return body.getBoundingClientRect().height - used;
    })));
}

function view(page: Page, name: string) {
  return page.getByRole("tab", { name: new RegExp(`^${name}`) });
}

test("the console loads without a console error and shows the sign-in", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Who is at the line?" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("every view is reachable, and by number key", async ({ page }) => {
  await signIn(page, "nav.tester");
  // Driven off VIEWS itself: a second copy of the list here is what silently goes stale the
  // next time a view is inserted in the middle.
  for (const n of VIEWS) {
    await view(page, n).click();
    await expect(page.locator(".page")).not.toBeEmpty();
    /* Two panels in a row both marked `grow` is 764px of void under whichever one cannot fill it —
       on a control panel that void reads as "nothing more to see", which is a lie. Only one panel
       in a row can take the slack, and it has to be the one whose content is unbounded. */
    expect(await slack(page), `${n} has a panel with a void under its content`).toBeLessThan(200);
  }
  for (const [i, n] of VIEWS.entries()) {
    if (i >= 10) break;                       // only the first ten have a number key
    await page.keyboard.press(i === 9 ? "0" : String(i + 1));
    await expect(view(page, n)).toHaveAttribute("aria-selected", "true");
  }
});

test("journey: open an engagement, register the landscape, see the write lock", async ({ page }) => {
  await signIn(page, "landscape.tester");
  const name = `Landscape ${Date.now()}`;
  await newEngagement(page, "Komatsu", name);
  await view(page, "Landscape").click();

  await page.getByRole("button", { name: "Register a system" }).click();
  await page.getByLabel("System id").fill("KOM-SF-DEV");
  await page.getByLabel("Product").fill("SuccessFactors");
  await page.getByLabel("Role").selectOption("TARGET");
  await page.getByLabel("Environment").selectOption("DEV");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(page.getByText("KOM-SF-DEV")).toBeVisible();

  // A legacy source is write-locked by the platform, and the console must say so in its own words.
  await page.getByRole("button", { name: "Register a system" }).click();
  await page.getByLabel("System id").fill("KOM-ECC-PRD");
  await page.getByLabel("Product").fill("ECC");
  await page.getByLabel("Role").selectOption("SOURCE_LEGACY");
  await page.getByLabel("Environment").selectOption("PROD");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(page.getByText("Read only").first()).toBeVisible();
});

test("journey: load signed intent, check it first, then plan the work", async ({ page, request }) => {
  const ir = await (await request.get("/", { failOnStatusCode: false })).ok();
  expect(ir).toBeTruthy();
  await signIn(page, "intent.tester");
  await newEngagement(page, "Komatsu", `Intent ${Date.now()}`);
  await view(page, "Intent").click();
  await expect(page.getByRole("heading", { name: "No signed intent yet" })).toBeVisible();

  await page.getByRole("button", { name: "Load intent" }).click();
  const records = JSON.stringify([{
    object: "PayComponent", product: "SuccessFactors", system_binding: "KOM-SF-DEV",
    tier: "A", intent: { code: "BASIC", name: "Basic Salary" },
    source: { workbook: "KOM-COMP-01.xlsx", signed_by: "komatsu.hr", date: "2026-02-02" },
  }]);
  await page.getByLabel("Records (JSON array)").fill(records);
  await page.getByRole("button", { name: "Check it" }).click();
  await expect(page.locator(".verbatim")).toContainText("check clean");
  await page.getByRole("button", { name: "Load it" }).click();
  await expect(page.getByText("PayComponent")).toBeVisible();

  await view(page, "Work").click();
  await expect(page.getByText("Take before-snapshot").first()).toBeVisible();
});

test("journey: the platform's refusal is quoted, not reworded", async ({ page }) => {
  await signIn(page, "refusal.tester");
  await newEngagement(page, "Komatsu", `Refusal ${Date.now()}`);
  await view(page, "Decisions").click();

  await page.getByRole("button", { name: "Raise a decision" }).click();
  await page.getByLabel("Reference").fill("DP-B11");
  await page.getByLabel("Kind").selectOption("STATUTORY");
  await page.getByLabel("Question").fill("What is the ZA negative-pay floor?");
  await page.getByLabel("Owner").fill("Komatsu HR");
  await page.getByRole("button", { name: "Raise it" }).click();
  await expect(page.getByText("DP-B11")).toBeVisible();

  // A statutory decision without a client evidence reference is refused server-side.
  await page.locator(".station", { hasText: "DP-B11" })
    .getByRole("button", { name: "Take this decision" }).click();
  await expect(page.getByLabel("Client evidence reference")).toBeVisible();
  await page.getByRole("textbox", { name: /^Decision/ }).fill("-5");
  await page.getByLabel("Client evidence reference").fill("KOM-POL-114");
  await page.getByRole("button", { name: "Record the decision" }).click();
  await expect(page.getByText("Taken").first()).toBeVisible();
});

test("journey: separation of duties refuses the executor's own approval, verbatim", async ({ page }) => {
  await signIn(page, "solo.operator");
  const name = `SoD ${Date.now()}`;
  await newEngagement(page, "Komatsu", name);
  await view(page, "Intent").click();
  await page.getByRole("button", { name: "Load intent" }).click();
  await page.getByLabel("Records (JSON array)").fill(JSON.stringify([{
    object: "PayComponent", product: "SuccessFactors", system_binding: "KOM-SF-DEV", tier: "A",
    intent: { code: "BASIC" }, source: { workbook: "w.xlsx", signed_by: "x", date: "2026-01-01" },
  }]));
  await page.getByRole("button", { name: "Load it" }).click();

  await view(page, "Work").click();
  await page.getByRole("button", { name: "Take before-snapshot" }).first().click();
  await page.getByRole("button", { name: "Execute", exact: true }).first().click();
  await page.getByRole("button", { name: "Validate" }).first().click();
  await page.getByRole("button", { name: "Approve", exact: true }).first().click();

  const modal = page.locator(".modal.refusal");
  await expect(modal).toBeVisible();
  await expect(modal.locator(".verbatim")).toContainText("solo.operator");
});

test("journey: the stop cord halts the line and the ledger records why", async ({ page }) => {
  await signIn(page, "cord.puller");
  await newEngagement(page, "Komatsu", `Cord ${Date.now()}`);

  await page.getByRole("button", { name: "Stop cord" }).click();
  await page.getByLabel("Reason").fill("Payroll parallel run mismatch on three components.");
  await page.getByRole("button", { name: "Pull the cord" }).click();

  await expect(page.getByText("The line is stopped.")).toBeVisible();
  await expect(page.locator(".verbatim")).toContainText("parallel run mismatch");

  await view(page, "Ledger").click();
  await expect(page.getByText("Line stopped").first()).toBeVisible();

  await page.getByRole("button", { name: "Line stopped" }).click();
  await page.getByLabel("What was done about it").fill("Mismatch traced to a stale source extract.");
  await page.getByRole("button", { name: "Release the line" }).click();
  await expect(page.getByText("The line is stopped.")).toHaveCount(0);
});

test("journey: evidence verifies offline and the procedure is published", async ({ page }) => {
  await signIn(page, "audit.tester");
  await view(page, "Evidence").click();
  await expect(page.getByText(/The chain verifies|The chain breaks/)).toBeVisible();
  await expect(page.getByText("How to verify this yourself")).toBeVisible();
  await expect(page.locator(".verbatim").last()).not.toBeEmpty();
  await expect(page.getByRole("button", { name: "Download bundle" })).toBeEnabled();
});

test("journey: the ledger is searchable and every link shows its hash", async ({ page }) => {
  await signIn(page, "ledger.tester");
  await view(page, "Ledger").click();
  await expect(page.locator(".hash").first()).toBeVisible();
  await page.getByLabel("Filter the ledger").fill("zzz-no-such-task");
  await expect(page.getByText("Nothing matches that filter.")).toBeVisible();
});

test("an auditor gets read access and no write controls", async ({ page }) => {
  await signIn(page, "read.only", ["auditor"]);
  await expect(page.getByRole("button", { name: "New engagement" })).toBeVisible();
  await view(page, "Landscape").click();
  await expect(page.getByRole("button", { name: "Register a system" })).toBeDisabled();
  await view(page, "Decisions").click();
  await expect(page.getByRole("button", { name: "Raise a decision" })).toBeDisabled();
});

test("the session survives a reload, an expired one does not, and sign out clears it", async ({ page }) => {
  await signIn(page, "persist.tester");
  await page.reload();
  await expect(page.locator(".topbar")).toContainText("persist.tester");

  // An expired token must sign the operator out on load rather than 401 on the first call.
  await page.evaluate(() => {
    const raw = sessionStorage.getItem("jidoka.session")!;
    const held = JSON.parse(raw);
    const [body, sig] = held.token.split(".");
    const claims = JSON.parse(atob(body.replace(/-/g, "+").replace(/_/g, "/")));
    claims.exp = Math.floor(Date.now() / 1000) - 60;
    const b64 = btoa(JSON.stringify(claims)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    sessionStorage.setItem("jidoka.session", JSON.stringify({ ...held, token: `${b64}.${sig}` }));
  });
  await page.reload();
  await expect(page.getByRole("button", { name: "Enter the console" })).toBeVisible();

  await signIn(page, "persist.tester");
  await page.getByRole("button", { name: "Sign out" }).click();
  expect(await page.evaluate(() => sessionStorage.getItem("jidoka.session"))).toBeNull();
});

/* The rail is the one element BRAND says is never scrolled away, so a viewport that pushes a lamp
   off it is a defect and not a small one: at 390px the Ledger, Evidence and Milestones tabs were
   past the right edge, unclickable, on a platform whose argument is the audit trail. */
test("every lamp on the rail is reachable on a phone, and nothing pushes the page sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "a.builder", ["approver", "auditor"]);
  for (const tab of await page.getByRole("tab").all()) {
    await tab.click({ timeout: 3000 });
    const slop = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(slop, `${await tab.getAttribute("title")} overflows`).toBeLessThanOrEqual(1);
  }
});
