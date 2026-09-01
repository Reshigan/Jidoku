/* Screenshot every screen, signed in, against the live API. Visual review, not assertion. */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { readFileSync } from "node:fs";

/* Driven off VIEWS in src/ui.tsx: a second copy of the list is what silently misses a new screen.
   Read rather than imported — node cannot load .tsx, and a build step for one array is not worth it. */
const VIEWS = JSON.parse(
  readFileSync(new URL("../src/ui.tsx", import.meta.url), "utf8")
    .match(/export const VIEWS = (\[[^\]]*\])/)[1].replace(/'/g, '"'),
);

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

// Pick the fullest engagement, else every screen shows an empty state and reviews nothing.
const EID = process.env.SHOT_EID;
if (EID) { await page.selectOption("header select", EID); await page.waitForTimeout(800); }

for (const [i, v] of VIEWS.entries()) {
  await page.getByRole("tab", { name: new RegExp(`^${v}`) }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${String(i + 1).padStart(2, "0")}-${v.toLowerCase()}.png`, fullPage: true });
}
console.log(errors.length ? `console errors:\n${errors.join("\n")}` : "no console errors");
await b.close();
