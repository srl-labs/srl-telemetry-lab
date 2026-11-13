// Smoke test of the deployed lab: telemetry, logs, alerts and the dashboard.
//
// usage: node tools/smoke-test.mjs
//
// environment:
//   GRAFANA, PROMETHEUS, LOKI  URLs of the lab, default localhost:3000, :9090, :3100
//   START_TRAFFIC=1            start the client traffic once BGP is up
//   TIMEOUT                    seconds to wait for the fabric to converge, default 420
//
// Screenshots of the dashboard tabs go to tools/smoke-test-results.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.dirname(here);
const results = path.join(here, "smoke-test-results");
const GRAFANA = process.env.GRAFANA ?? "http://localhost:3000";
const PROMETHEUS = process.env.PROMETHEUS ?? "http://localhost:9090";
const LOKI = process.env.LOKI ?? "http://localhost:3100";
const TIMEOUT = Number(process.env.TIMEOUT ?? 420) * 1000;
const DASHBOARD = "ce11ch1funwu8d";
const TABS = ["Fabric", "Switches", "Ports", "EVPN", "Logs"];

// What the fabric looks like when it is up.
const BGP_SESSIONS = 24; // 2 x 3 underlay + 2 x 3 overlay, counted on both ends
const SWITCHES = 5;
const MAC_ENTRIES = 9; // 3 MACs on each of the 3 leaves

const failures = [];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function check(name, ok, detail = "") {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${detail ? `: ${detail}` : ""}`);
  if (!ok) failures.push(name);
}

async function promql(query) {
  const response = await fetch(`${PROMETHEUS}/api/v1/query?query=${encodeURIComponent(query)}`);
  const body = await response.json();
  if (body.status !== "success") throw new Error(`${query}: ${body.error}`);
  return body.data.result;
}

async function scalar(query) {
  const result = await promql(query).catch(() => []);
  return result.length ? Number(result[0].value[1]) : NaN;
}

async function logql(query) {
  const response = await fetch(`${LOKI}/loki/api/v1/query?query=${encodeURIComponent(query)}`);
  const body = await response.json();
  return body.data?.result ?? [];
}

// Polls until the value matches, and reports the last value it saw.
async function waitFor(name, read, ok, timeout = TIMEOUT) {
  const deadline = Date.now() + timeout;
  let value;
  for (;;) {
    value = await read().catch((error) => error.message);
    if (ok(value) || Date.now() > deadline) break;
    await sleep(5000);
  }
  check(name, ok(value), JSON.stringify(value));
  return ok(value);
}

// --- telemetry ---------------------------------------------------------------
console.log("waiting for the fabric to converge");
const bgpUp = await waitFor(
  `${BGP_SESSIONS} BGP sessions established`,
  () => scalar("count(network_instance_protocols_bgp_neighbor_session_state == 6)"),
  (value) => value === BGP_SESSIONS
);
await waitFor(
  `${SWITCHES} switches without problems`,
  async () => {
    const result = await promql("srl:switch:problems");
    return { switches: result.length, problems: result.reduce((sum, r) => sum + Number(r.value[1]), 0) };
  },
  (value) => value.switches === SWITCHES && value.problems === 0,
  60000
);

if (bgpUp && process.env.START_TRAFFIC === "1") {
  console.log("starting the client traffic");
  execFileSync("bash", [path.join(repo, "traffic.sh"), "start", "all"], { stdio: "inherit" });
}
await waitFor(
  "client traffic flows",
  () => scalar('sum(interface_traffic_rate_in_bps{source=~"leaf.*", interface_name="e1-1"})'),
  (value) => value > 1e6,
  120000
);
await waitFor(
  `${MAC_ENTRIES} MAC table entries`,
  () => scalar("count(network_instance_bridge_table_mac_table_mac_type)"),
  (value) => value === MAC_ENTRIES,
  120000
);
await waitFor(
  "EVPN routes collected",
  () => scalar("count({__name__=~\".*_evpn_rib_in_out_rib_in_post_.*_used_route\"} == 1)"),
  (value) => value > 0,
  60000
);
await waitFor(
  "cabled ports carry their description",
  () => scalar("count(srl:interface:in_use{description!=\"\"})"),
  (value) => value === 15,
  60000
);

// --- logs and alerts -----------------------------------------------------------
// A configuration change on leaf1 must arrive in Loki as a parsed event.
execFileSync("bash", [path.join(repo, "scenario.sh"), "commit", "leaf1"], { stdio: "ignore" });
await waitFor(
  "commit on leaf1 logged as an event in Loki",
  async () =>
    (await logql('sum(count_over_time({job="syslog", kind="event", event="commitSucceeded", source="leaf1"}[2m]))'))[0]
      ?.value[1] ?? 0,
  (value) => Number(value) > 0,
  60000
);
await waitFor(
  "no alert firing",
  async () => (await promql('ALERTS{alertstate="firing"}')).map((r) => `${r.metric.alertname} ${r.metric.source ?? ""}`),
  (value) => Array.isArray(value) && value.length === 0,
  120000
);

// --- dashboard -----------------------------------------------------------------
mkdirSync(results, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1700, height: 1300 } });
const queryErrors = [];
page.on("response", async (response) => {
  if (!response.url().includes("/api/ds/query")) return;
  const body = await response.json().catch(() => null);
  for (const [ref, result] of Object.entries(body?.results ?? {})) {
    if (result.error) queryErrors.push(`${ref}: ${result.error}`);
  }
});
page.on("pageerror", (error) => queryErrors.push(`page error: ${error.message}`));

await page.goto(`${GRAFANA}/d/${DASHBOARD}/x?orgId=1&kiosk`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(10000);
for (const tab of TABS) {
  const button = page.getByRole("tab", { name: tab, exact: true });
  if (!(await button.count())) {
    check(`dashboard tab ${tab}`, false, "missing");
    continue;
  }
  queryErrors.length = 0;
  await button.first().click();
  await page.waitForTimeout(8000);
  await page.screenshot({ path: path.join(results, `${tab}.png`), fullPage: true });
  const panelErrors = await page.locator('[data-testid*="Panel status error"]').count();
  check(
    `dashboard tab ${tab}`,
    panelErrors === 0 && queryErrors.length === 0,
    [panelErrors ? `${panelErrors} panel errors` : "", ...queryErrors].filter(Boolean).join("; ")
  );
}
await browser.close();

console.log(failures.length ? `\n${failures.length} check(s) failed: ${failures.join(", ")}` : "\nall checks passed");
process.exit(failures.length ? 1 : 0);
