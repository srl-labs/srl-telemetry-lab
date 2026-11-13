// Exports the topology map of the lab as a Grafana bundle for the flow panel.
//
// It drives the topology viewer of containerlab-app (https://github.com/srl-labs/containerlab-app)
// in its UI harness, the same export as Export SVG > Grafana bundle in the app,
// and writes topology-bundle/st.grafana.json next to this script.
//
// usage: CLAB_UI=<containerlab-app>/packages/clab-ui node export-bundle.mjs
//   with the harness running: pnpm --dir "$CLAB_UI" run dev:ui-harness
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "..", "package.json"));
const { chromium } = require("playwright");

const HARNESS = process.env.HARNESS ?? "http://127.0.0.1:5184";
const topoPath = path.join(here, "..", "..", "st.clab.yml");
const outDir = path.join(here, "topology-bundle");
const fileName = path.basename(topoPath);
const yaml = readFileSync(topoPath, "utf8");
const annotations = JSON.parse(readFileSync(`${topoPath}.annotations.json`, "utf8"));

// The canvas uses boxed nodes, the Grafana map the telemetry style: icons with
// port bubbles and rate labels on the links. The annotations file on disk
// stays untouched; these changes only apply to the export.
annotations.viewerSettings = {
  ...annotations.viewerSettings,
  nodeStyle: "icon",
  style: "telemetry-style",
  linkLabelMode: "telemetry-style",
  showRateLabels: true
};
// The texts, arrows, groups and script buttons belong to the canvas. build-dashboard.py
// draws the addressing labels from the exported geometry, and the telemetry
// and logging stack has no data-plane links, so it is left out of the export.
annotations.freeTextAnnotations = [];
annotations.freeShapeAnnotations = [];
annotations.groupStyleAnnotations = [];
annotations.scriptButtonAnnotations = [];
// The exporter places the rate labels on their link halves.
annotations.trafficRateAnnotations = [];
// The canvas leaves room between the spines and the leaves for its rate
// labels; the Grafana map is more compact, with its own positions.
const POSITIONS = {
  spine1: { x: 30, y: -40 },
  spine2: { x: 250, y: -40 },
  leaf1: { x: -80, y: 140 },
  leaf2: { x: 140, y: 140 },
  leaf3: { x: 360, y: 140 },
  client1: { x: -80, y: 280 },
  client2: { x: 140, y: 280 },
  client3: { x: 360, y: 280 }
};
for (const node of annotations.nodeAnnotations ?? []) {
  delete node.groupId;
  if (node.id in POSITIONS) node.position = { ...POSITIONS[node.id] };
  if (node.id.startsWith("spine")) node.labelPosition = "top";
  if (node.id.startsWith("leaf")) node.labelPosition = "left";
}
mkdirSync(outDir, { recursive: true });

// Traffic colour thresholds in kbit/s.
const THRESHOLDS = { Green: "10", Yellow: "500", Orange: "2000", Red: "5000" };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
page.on("pageerror", (error) => console.error("[pageerror]", error.message));

await page.goto(`${HARNESS}/?sessionId=st-export&devExplorer=0&templates=none`, {
  waitUntil: "domcontentloaded"
});
await page.waitForFunction(() => window.__DEV__?.rfInstance !== undefined, undefined, {
  timeout: 60000
});
await page.waitForTimeout(500);

await page.evaluate(
  async ({ fileName, yaml, annotations }) => {
    const dev = window.__DEV__;
    await dev.writeYamlFile(fileName, yaml);
    await dev.writeAnnotationsFile(fileName, annotations);
    await dev.loadTopologyFile(fileName);
  },
  { fileName, yaml, annotations }
);
await page.waitForFunction(
  (expected) => window.__DEV__.getCurrentFile().endsWith(expected),
  fileName
);
await page.waitForFunction(
  (count) => window.__DEV__.rfInstance.getNodes().length >= count,
  (annotations.nodeAnnotations ?? []).length
);
await page.waitForTimeout(1500);
await page.evaluate(() => window.__DEV__.rfInstance.fitView({ padding: 0.1 }));
await page.waitForTimeout(800);

await page.locator('[data-testid="navbar-capture"]').click();
const modal = page.locator('[data-testid="svg-export-modal"]');
await modal.waitFor({ state: "visible" });
await modal.getByRole("checkbox", { name: "Grafana bundle" }).check();
await page.locator('[data-testid="svg-export-grafana-advanced-btn"]').click();

const settings = page.locator('[data-testid="svg-export-grafana-settings-modal"]');
await settings.waitFor({ state: "visible" });
await settings.getByLabel("Traffic threshold unit").click();
await page.getByRole("option", { name: "kbit/s" }).click();
// Raise the upper bounds first so the values stay ascending while typing.
for (const name of ["Red", "Orange", "Yellow", "Green"]) {
  const input = settings.getByLabel(`${name} threshold`);
  await input.fill(THRESHOLDS[name]);
}
await settings.getByRole("checkbox", { name: "Add traffic legend (top-left)" }).check();
await settings.getByRole("button", { name: "Close" }).last().click();
await settings.waitFor({ state: "hidden" });

await page.evaluate(() => {
  window.__CLAB_UI_HARNESS_MESSAGES__ = [];
});
await page.locator('[data-testid="svg-export-btn"]').click();

const handle = await page.waitForFunction(() => {
  const messages = window.__CLAB_UI_HARNESS_MESSAGES__ ?? [];
  return (
    messages.find(
      (message) =>
        message?.command === "export-svg-grafana-bundle" && typeof message.svgContent === "string"
    ) ?? null
  );
});
const bundle = await handle.jsonValue();
// The dashboard holds the SVG and the panel configuration; build-dashboard.py
// takes the flow panel from it.
writeFileSync(path.join(outDir, `${bundle.baseName}.grafana.json`), `${JSON.stringify(JSON.parse(bundle.dashboardJson), null, 2)}\n`);
console.log(
  `exported ${bundle.baseName}: svg=${bundle.svgContent.length}B json=${bundle.dashboardJson.length}B yaml=${bundle.panelYaml.length}B`
);

await browser.close();
