/* Screenshot every screen, signed in, against the live API. Visual review, not assertion. */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const OUT = process.argv[2] ?? "/tmp/claude-501/shots";
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 950 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

await page.goto("http://localhost:5273/");
await page.screenshot({ path: `${OUT}/00-signin.png`, fullPage: true });

await page.getByLabel("Name").fill("a.builder");
for (const r of ["approver", "auditor"]) await page.getByRole("button", { name: r, exact: true }).click();
await page.getByRole("button", { name: "Enter the console" }).click();
await page.waitForTimeout(800);

for (const [i, v] of ["Line", "Work", "Configure", "Decisions", "Intent", "Landscape", "Ledger", "Evidence", "Milestones"].entries()) {
  await page.getByRole("tab", { name: new RegExp(`^${v}`) }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${String(i + 1).padStart(2, "0")}-${v.toLowerCase()}.png`, fullPage: true });
}
console.log(errors.length ? `console errors:\n${errors.join("\n")}` : "no console errors");
await b.close();
