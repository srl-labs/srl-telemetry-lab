# Dashboard build

The Grafana dashboard of the lab, [configs/grafana/dashboards/telemetry-dashboard.json](../../configs/grafana/dashboards/telemetry-dashboard.json), is generated. Change the scripts here rather than the JSON file, and rebuild.

| File | Role |
| --- | --- |
| `build-dashboard.py` | Defines every panel, the tabs and the variables, and writes the dashboard and the flow panel sources in [configs/grafana/flow_panels](../../configs/grafana/flow_panels). |
| `export-bundle.mjs` | Exports the topology map from the topology file as a Grafana bundle for the flow panel. |
| `topology-bundle/st.grafana.json` | The exported bundle: the topology SVG and the flow panel configuration. |
| `faceplates/` | Faceplates of the 7220 IXR-D2L and IXR-D3L for the front panel view. |

## Rebuild the dashboard

The build hands the panels to Grafana to convert them to its dashboard v2 format (tabs), so the lab must be running:

```bash
containerlab deploy -t st.clab.yml
python3 tools/dashboard/build-dashboard.py
```

Grafana picks up the new file within 10 seconds.

## Export the topology map again

Needed when the topology changes: nodes, links or their position in [st.clab.yml.annotations.json](../../st.clab.yml.annotations.json).

The export runs the topology viewer of [containerlab-app](https://github.com/srl-labs/containerlab-app) in its UI harness, with the same Grafana bundle export as **Export SVG > Grafana bundle** in the [containerlab app](https://containerlab.app):

```bash
# in a checkout of containerlab-app
pnpm install
pnpm --dir packages/clab-ui run dev:ui-harness

# in this repository
npm ci --prefix tools
npx --prefix tools playwright install chromium
node tools/dashboard/export-bundle.mjs
python3 tools/dashboard/build-dashboard.py
```

The canvas shows boxed nodes, groups, texts and script buttons; the export switches to the telemetry style (icons with port bubbles and rate labels) and leaves the rest out. `build-dashboard.py` then adds the AS numbers and addresses, and lets the client ends of the access links follow the leaf ports, as the clients are not telemetry targets.

Traffic colour thresholds of the map, in kbit/s: green from 10, yellow from 500, orange from 2000, red from 5000.
