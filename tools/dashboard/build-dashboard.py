#!/usr/bin/env python3
"""Build the Grafana dashboard of the lab.

Writes configs/grafana/dashboards/telemetry-dashboard.json and the flow panel
sources in configs/grafana/flow_panels. Grafana converts the panels to its
dashboard v2 format, so the lab must be running. See README.md next to this file.

usage: build-dashboard.py [--grafana http://localhost:3000]
"""
import argparse
import base64
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--grafana", default=os.environ.get("GRAFANA", "http://localhost:3000"), help="Grafana of the running lab")
parser.add_argument("--bundle", default=os.path.join(HERE, "topology-bundle", "st.grafana.json"), help="Grafana bundle exported from the topology")
args = parser.parse_args()

bundle_path = args.bundle
d2l_path = os.path.join(HERE, "faceplates", "d2l.webp")
d3l_path = os.path.join(HERE, "faceplates", "d3l.webp")
out_path = os.path.join(REPO, "configs", "grafana", "dashboards", "telemetry-dashboard.json")
flow_dir = os.path.join(REPO, "configs", "grafana", "flow_panels")
GRAFANA = args.grafana

PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}

# The clients are not telemetry targets: their end of the access links is
# driven by what the leaf sees on its client-facing port.
CLIENT_PORTS = {
    "client1:eth1": "leaf1:e1-1",
    "client2:eth1": "leaf2:e1-1",
    "client3:eth1": "leaf3:e1-1",
}
# Name pills left of the leaf icons move outwards to clear the icon.
NODE_LABEL_SHIFTS = {"leaf1": -6, "leaf2": -6, "leaf3": -6}
# node: lines written to the right of the icon
NODE_LABELS = {
    "spine1": ["AS 201", "10.0.2.1"],
    "spine2": ["AS 202", "10.0.2.2"],
    "leaf1": ["AS 101", "10.0.1.1"],
    "leaf2": ["AS 102", "10.0.1.2"],
    "leaf3": ["AS 103", "10.0.1.3"],
    "client1": ["172.17.0.1/24"],
    "client2": ["172.17.0.2/24"],
    "client3": ["172.17.0.3/24"],
}
# Cabled ports per faceplate: node -> (chassis, ports)
FRONT_PANEL = {
    "spine1": ("d3l", (1, 2, 3)),
    "spine2": ("d3l", (1, 2, 3)),
    "leaf1": ("d2l", (1, 49, 50)),
    "leaf2": ("d2l", (1, 49, 50)),
    "leaf3": ("d2l", (1, 49, 50)),
}

MARKERS = (
    "Vertical markers show SR Linux events from the logs: orange a port going up or down, "
    "red a BGP session changing state, blue a configuration commit. Hover a marker for the message."
)

# Recording rules of configs/prometheus/rules.yml.
# IN_USE keeps the cabled ports (the ports that have carried traffic) of a
# port metric. WITH_DESC does the same and adds the port description as label;
# put the left side in parentheses when it is more than a metric selector.
IN_USE = "and on(source, interface_name) srl:interface:in_use"
WITH_DESC = "* on(source, interface_name) group_left(description) srl:interface:in_use"
# BGP session state 6 is established, see the text-to-number processor of gnmic.
ESTABLISHED = 6
BGP_STATE_MAPPING = [
    {
        "options": {
            "1": {"color": "red", "index": 0, "text": "idle"},
            "2": {"color": "orange", "index": 1, "text": "connect"},
            "3": {"color": "orange", "index": 2, "text": "active"},
            "4": {"color": "orange", "index": 3, "text": "opensent"},
            "5": {"color": "orange", "index": 4, "text": "openconfirm"},
            "6": {"color": "green", "index": 5, "text": "established"},
        },
        "type": "value",
    }
]
# VTEP 10.0.1.N is the system address of leafN.
def vtep_to_leaf(expr, source_label, target_label):
    return f'label_replace({expr}, "{target_label}", "leaf$1", "{source_label}", "(?:vtep )?10\\\\.0\\\\.1\\\\.(\\\\d+)")'


def target(ref, expr, legend, ds=PROM, **extra):
    return {
        "datasource": ds,
        "editorMode": "code",
        "expr": expr,
        "legendFormat": legend,
        "range": True,
        "refId": ref,
        **extra,
    }


def instant(ref, expr, legend, **extra):
    return target(ref, expr, legend, instant=True, range=False, **extra)


def timeseries(panel_id, title, grid, targets, description="", unit="bps", legend="right", **custom):
    return {
        "datasource": PROM,
        "description": description,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisBorderShow": False,
                    "axisPlacement": "auto",
                    "drawStyle": "line",
                    "fillOpacity": 12,
                    "gradientMode": "opacity",
                    "lineInterpolation": "smooth",
                    "lineWidth": 2,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                    "thresholdsStyle": {"mode": "off"},
                    **custom,
                },
                "mappings": [],
                "min": 0,
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": unit,
            },
            "overrides": [],
        },
        "gridPos": grid,
        "id": panel_id,
        "options": {
            "legend": {
                "calcs": ["lastNotNull", "max"],
                "displayMode": "table",
                "placement": legend,
                "showLegend": True,
                "sortBy": "Name",
                "sortDesc": False,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
        "title": title,
        "type": "timeseries",
    }


def stat(panel_id, title, grid, targets, defaults, description="", ds=PROM, **options):
    return {
        "datasource": ds,
        "description": description,
        "fieldConfig": {"defaults": defaults, "overrides": options.pop("overrides", [])},
        "gridPos": grid,
        "id": panel_id,
        "options": {
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "value_and_name",
            "wideLayout": True,
            **options,
        },
        "targets": targets,
        "title": title,
        "type": "stat",
    }


def gauge(panel_id, title, grid, expr):
    return {
        "datasource": PROM,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "decimals": 0,
                "mappings": [],
                "max": 100,
                "min": 0,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "orange", "value": 70},
                        {"color": "red", "value": 90},
                    ],
                },
                "unit": "percent",
            },
            "overrides": [],
        },
        "gridPos": grid,
        "id": panel_id,
        "options": {
            "minVizHeight": 75,
            "minVizWidth": 75,
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
            "sizing": "auto",
        },
        "targets": [target("A", expr, "__auto")],
        "title": title,
        "type": "gauge",
    }


def override(name, properties):
    return {
        "matcher": {"id": "byName", "options": name},
        "properties": [{"id": key, "value": value} for key, value in properties.items()],
    }


STATE_MAPPING = [
    {
        "options": {
            "0": {"color": "red", "index": 0, "text": "down"},
            "1": {"color": "green", "index": 1, "text": "up"},
        },
        "type": "value",
    }
]
STATE_THRESHOLDS = {
    "mode": "absolute",
    "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}],
}
PLAIN_THRESHOLDS = {"mode": "absolute", "steps": [{"color": "text", "value": None}]}
PLAIN = {"color": {"mode": "thresholds"}, "mappings": [], "noValue": "-", "thresholds": PLAIN_THRESHOLDS}
ALERT_IF_ANY = {
    "color": {"mode": "thresholds"},
    "mappings": [],
    "thresholds": {
        "mode": "absolute",
        "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}],
    },
}


# --- topology flow panel generated from the topology file --------------------
flow = json.load(open(bundle_path))["panels"][0]
flow.update(
    {
        "datasource": PROM,
        "description": (
            "Live view of the fabric. Each half of a link is coloured by the traffic rate "
            "leaving that end, the port bubbles by oper-state. Generated with the Grafana "
            "bundle export of containerlab."
        ),
        "id": 2,
        "title": "Fabric topology",
    }
)
for flow_target in flow["targets"]:
    flow_target["datasource"] = PROM

panel_config = flow["options"]["panelConfig"]
# Without a label color the rate labels keep currentColor, the text color of
# the Grafana theme, light or dark.
panel_config, label_colours = re.subn(
    r"\n    labelColor:\n      thresholds: \*thresholds-rate-label", "", panel_config
)
assert label_colours == 18, label_colours
panel_config = panel_config.replace(
    '  thresholds-rate-label: &thresholds-rate-label\n    - { color: "white", level: 0 }\n', ""
)
assert "thresholds-rate-label" not in panel_config
for client_port, leaf_port in CLIENT_PORTS.items():
    for old, new in (
        (f'dataRef: "{client_port}:out"', f'dataRef: "{leaf_port}:in"'),
        (f'dataRef: "oper-state:{client_port}"', f'dataRef: "oper-state:{leaf_port}"'),
    ):
        assert old in panel_config, old
        panel_config = panel_config.replace(old, new)
flow["options"]["panelConfig"] = panel_config

# The flow panel drops the dominant-baseline attribute when it sanitises the SVG,
# which leaves port numbers and node names sitting above their bubbles and pills.
# An explicit dy offset centres the text the same way and survives.
topology_svg = flow["options"]["svg"]
assert ' dy="' not in topology_svg.split('class="grafana-traffic-legend"')[0]
topology_svg = topology_svg.replace(' dominant-baseline="central"', ' dy="0.35em"')
topology_svg = topology_svg.replace(' dominant-baseline="middle"', ' dy="0.32em"')
assert "dominant-baseline" not in topology_svg

# Follow the light and the dark theme of Grafana. The export draws light text
# and outlines for a dark canvas; they take the text color of the theme
# (currentColor) instead, the rate labels the "text" color of the theme.
for old, new in (
    ('stroke="#ddf8ff"', 'stroke="currentColor"'),  # outline of the node icons
    (' style="color: rgb(255, 255, 255); filter: drop-shadow(rgba(0, 0, 0, 0.95) 0px 0px 1px);"', ""),  # rate labels
):
    assert old in topology_svg, old
    topology_svg = topology_svg.replace(old, new)
topology_svg, legend_entries = re.subn(
    r'fill="#e7edf7" stroke="rgba\(0, 0, 0, 0\.65\)" stroke-width="[\d.]+" paint-order="stroke"',
    'fill="currentColor"',
    topology_svg,
)
assert legend_entries == 5, legend_entries


def shift_node_label(svg, node_id, dx):
    """Move a node name pill sideways so it clears the node icon."""
    pattern = re.compile(
        r'(<g class="export-node topology-node" data-id="%s">.*?</svg></g><rect x=")([-\d.]+)'
        r'("[^>]*/><text x=")([-\d.]+)' % re.escape(node_id),
        re.S,
    )
    match = pattern.search(svg)
    assert match, node_id
    shifted = (
        match.group(1)
        + f"{float(match.group(2)) + dx:g}"
        + match.group(3)
        + f"{float(match.group(4)) + dx:g}"
    )
    return svg[: match.start()] + shifted + svg[match.end() :]


for node, dx in NODE_LABEL_SHIFTS.items():
    topology_svg = shift_node_label(topology_svg, node, dx)


def offset_vertical_rate_labels(svg, gap=6):
    """Rate labels of vertical links sit on the line; move them beside it."""

    def fix(match):
        x1, x2 = float(match.group(2)), float(match.group(4))
        if abs(x1 - x2) > 1e-6:
            return match.group(0)
        head = match.group(0)
        head = re.sub(r'<text x="[-\d.]+"', f'<text x="{x1 + gap:g}"', head, count=1)
        return head.replace('text-anchor="middle"', 'text-anchor="start"', 1)

    pattern = re.compile(
        r'(<g class="grafana-traffic-half"[^>]*><path d="M ([-\d.]+) ([-\d.]+) L ([-\d.]+) ([-\d.]+)"'
        r'[^>]*/><text [^>]*>)'
    )
    return pattern.sub(fix, svg)


topology_svg = offset_vertical_rate_labels(topology_svg)

# --- addressing labels ----------------------------------------------------------
LABEL_FONT = "Helvetica, Arial, sans-serif"
NODE_LABEL_GAP = 7

icons = {
    m.group(1): tuple(float(m.group(i)) for i in range(2, 6))
    for m in re.finditer(
        r'data-id="(\w+)"><g transform="[^"]*"><svg class="export-node-icon" '
        r'x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"',
        topology_svg,
    )
}
assert set(NODE_LABELS) <= set(icons), icons.keys()


def label_text(x, y, text, size, anchor, weight="normal"):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" dy="0.35em" font-size="{size}" font-weight="{weight}" '
        # in the text color of the theme, a little lighter
        f'font-family="{LABEL_FONT}" fill="currentColor" fill-opacity="0.7" text-anchor="{anchor}">{text}</text>'
    )


labels = []
for node, lines in NODE_LABELS.items():
    icon_x, icon_y, icon_w, icon_h = icons[node]
    x = icon_x + icon_w + NODE_LABEL_GAP
    size = 8
    line_height = size * 1.45
    first_y = icon_y + icon_h / 2 - line_height * (len(lines) - 1) / 2
    for index, line in enumerate(lines):
        labels.append(label_text(x, first_y + index * line_height, line, size, "start"))

# The labels go at the end of the graph layer, which uses the icon coordinates.
graph_end = '</g><g class="grafana-traffic-legend"'
assert topology_svg.count(graph_end) == 1
topology_svg = topology_svg.replace(graph_end, "".join(labels) + graph_end)
# Room on the right for the address of the right-most client.
view_box = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', topology_svg)
vx, vy, vw, vh = (float(v) for v in view_box.groups())
topology_svg = topology_svg.replace(view_box.group(0), f'viewBox="{vx:g} {vy:g} {vw + 130:g} {vh:g}"', 1)
assert "foreignObject" not in topology_svg
flow["options"]["svg"] = topology_svg

# --- front panel view ---------------------------------------------------------
# One faceplate per switch with the cabled ports overlaid and coloured by
# oper-state. Port centres are in faceplate pixels.
CHASSIS = {
    "d2l": {
        "model": "7220 IXR-D2L",
        "image": d2l_path,
        "height": 149,
        # 48 SFP28 cages in three rows, then QSFP28 cages 49 (top) and 50 (bottom).
        "port": lambda p: (
            (135 + ((p - 1) // 3 // 2) * 86 + ((p - 1) // 3 % 2) * 37, (38, 73, 109)[(p - 1) % 3], 32, 18)
            if p <= 48
            else (894.5, (78.5, 113.5)[(p - 49) % 2], 44, 20)
        ),
    },
    "d3l": {
        "model": "7220 IXR-D3L",
        "image": d3l_path,
        "height": 152,
        # 32 QSFP28 cages in two rows, odd ports on top.
        "port": lambda p: (220.5 + ((p - 1) // 2) * 49, (69.5, 102.5)[(p - 1) % 2], 44, 20),
    },
}
CHASSIS_W = 1280


def build_front_panel():
    images = {
        name: base64.b64encode(open(spec["image"], "rb").read()).decode() for name, spec in CHASSIS.items()
    }
    block_h, margin, title_h = 186, 20, 30
    width = CHASSIS_W + 2 * margin
    height = len(FRONT_PANEL) * block_h + 4
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">',
    ]
    cells = [
        "---",
        "anchors:",
        "  thresholds-operstate: &thresholds-operstate",
        '    - { color: "red", level: 0 }',
        '    - { color: "green", level: 1 }',
        'cellIdPreamble: "cell-"',
        "cells:",
    ]
    for index, (node, (chassis, ports)) in enumerate(FRONT_PANEL.items()):
        spec = CHASSIS[chassis]
        top = 4 + index * block_h
        plate_y = top + title_h
        svg.append(
            f'<text x="{margin}" y="{top + 21}" font-size="20" font-weight="600" '
            f'font-family="Helvetica, Arial, sans-serif" fill="currentColor">{node}'
            f'<tspan font-weight="400" fill-opacity="0.65" dx="10">{spec["model"]}</tspan></text>'
        )
        # The flow panel drops <use>, so every switch carries its own image.
        svg.append(
            f'<image x="{margin}" y="{plate_y}" width="{CHASSIS_W}" height="{spec["height"]}" '
            f'href="data:image/webp;base64,{images[chassis]}"/>'
        )
        for port in ports:
            cx, cy, w, h = spec["port"](port)
            x, y = margin + cx, plate_y + cy
            cell = f"front:{node}:e1-{port}"
            svg.append(
                f'<rect id="cell-{cell}" x="{x - w / 2:g}" y="{y - h / 2:g}" '
                f'width="{w}" height="{h}" rx="3" fill="#bec8d2" '
                f'stroke="rgba(0, 0, 0, 0.6)" stroke-width="1"/>'
                f'<text x="{x:g}" y="{y:g}" dy="0.35em" font-size="13" font-weight="700" '
                f'font-family="Helvetica, Arial, sans-serif" fill="#101418" '
                f'text-anchor="middle" pointer-events="none">{port}</text>'
            )
            cells += [
                f'  "{cell}":',
                f'    dataRef: "oper-state:{node}:e1-{port}"',
                "    fillColor:",
                "      thresholds: *thresholds-operstate",
            ]
    svg.append("</svg>")
    return "".join(svg), "\n".join(cells) + "\n"


front_svg, front_config = build_front_panel()

# --- panels -------------------------------------------------------------------
# Positions are set by the tabbed layout further down; the gridPos of the
# panels only matters for the conversion to the v2 dashboard format.
G = {"h": 4, "w": 4, "x": 0, "y": 0}

flow["options"]["timeSliderEnabled"] = False

front_panel = {
    "datasource": PROM,
    "description": "Faceplates of the five switches. The cabled ports are coloured by oper-state.",
    "gridPos": G,
    "id": 3,
    "options": {
        **flow["options"],
        "animationControlEnabled": False,
        "highlighterEnabled": False,
        "panelConfig": front_config,
        "svg": front_svg,
        "timeSliderEnabled": False,
    },
    "targets": [target("A", "interface_oper_state", "oper-state:{{source}}:{{interface_name}}")],
    "title": "Front panel view",
    "type": flow["type"],
}

# Problems per switch (recording rule): BGP sessions that are not established
# plus cabled ports that are down. 0 is healthy. Drives the status colour of
# the switch pickers.
HEALTH = "srl:switch:problems"
HEALTH_THRESHOLDS = {
    "mode": "absolute",
    "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}],
}


def table_query(ref, expr, ds=PROM):
    if ds == LOKI:
        return target(ref, expr, "", ds=LOKI, queryType="instant", range=False, instant=True)
    return instant(ref, expr, "", format="table")


def switch_buttons(panel_id, description):
    """A row of buttons, one per switch, outlined by the switch health."""
    return {
        "datasource": PROM,
        "description": description,
        "fieldConfig": {
            "defaults": {"color": {"mode": "thresholds"}, "thresholds": HEALTH_THRESHOLDS},
            "overrides": [],
        },
        "gridPos": G,
        "id": panel_id,
        "options": {
            "displayMode": "button",
            "variable": "Node",
            "name": "Node",
            "status": "Value",
            "padding": 4,
            "showLabel": True,
            "labelWidth": 10,
            "emptyValue": False,
            "persistent": False,
            "showResetButton": False,
        },
        "targets": [table_query("A", f'label_replace({HEALTH}, "Node", "$1", "source", "(.+)")')],
        "title": "",
        "transparent": True,
        "type": "volkovlabs-variable-panel",
    }


def tree_options(groups, name, extra=None):
    return {
        "displayMode": "table",
        "groups": groups,
        "name": name,
        # The plugin matches the raw field name of the status query.
        "status": "Value #B",
        "header": True,
        "filter": True,
        "alwaysVisibleFilter": False,
        "favorites": {"enabled": False},
        "selectedValues": {"showSelected": False},
        "statusSort": False,
        "showTotal": False,
        "groupSelection": True,
        "showGroupTotal": True,
        "collapsedByDefault": False,
        "showName": False,
        "padding": 10,
        "tableViewPosition": "normal",
        "wordBreak": "normal",
        **(extra or {}),
    }


port_tree = {
    "datasource": PROM,
    "description": (
        "Pick switches and ports. A red dot marks a switch with a BGP session or a cabled port down."
    ),
    "fieldConfig": {
        "defaults": {"color": {"mode": "thresholds"}, "thresholds": HEALTH_THRESHOLDS},
        "overrides": [],
    },
    "gridPos": G,
    "id": 61,
    "options": tree_options(
        [{"name": "Ports", "items": [{"name": "Node", "source": "A"}, {"name": "Interface", "source": "A"}]}],
        "switch",
    ),
    "targets": [
        table_query(
            "A",
            'max by (Node, Interface) (label_replace(label_replace('
            f"interface_oper_state {IN_USE}, "
            '"Node", "$1", "source", "(.+)"), "Interface", "$1", "interface_name", "(.+)"))',
        ),
        table_query("B", f'label_replace({HEALTH}, "switch", "$1", "source", "(.+)")'),
    ],
    "title": "Switches and ports",
    "transformations": [{"id": "sortBy", "options": {"fields": {}, "sort": [{"field": "Node"}]}}],
    "type": "volkovlabs-variable-panel",
}

WARNING_LEVELS = 'level=~"warning|err|error|crit|alert|emerg"'
# SR Linux events (a port went down, a commit succeeded) as opposed to the
# debug traces of its applications, see configs/alloy/alloy-config.alloy.
EVENTS = 'kind="event"'
app_tree = {
    "datasource": LOKI,
    "description": "Pick SR Linux applications. An orange or red dot marks an application that logged warnings or errors.",
    "fieldConfig": {
        "defaults": {
            "color": {"mode": "thresholds"},
            "thresholds": {
                "mode": "absolute",
                "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 50}],
            },
        },
        "overrides": [],
    },
    "gridPos": G,
    "id": 62,
    "options": tree_options(
        [{"name": "Applications", "items": [{"name": "Application", "source": "A"}]}],
        "app",
    ),
    "targets": [
        table_query(
            "A",
            'sum by (Application) (count_over_time({job="syslog", source=~"$Node", kind=~"$Kind"} '
            '| label_format Application="{{.application}}" [$__range]))',
            ds=LOKI,
        ),
        table_query(
            "B",
            f'sum by (app) (count_over_time({{job="syslog", source=~"$Node", kind=~"$Kind", {WARNING_LEVELS}}} '
            '| label_format app="{{.application}}" [$__range]))',
            ds=LOKI,
        ),
    ],
    "title": "Applications",
    "type": "volkovlabs-variable-panel",
}


def bgp_table(panel_id):
    """One line per BGP session of the default network instance."""
    keys = "source, neighbor_peer_address"

    def query(ref, expr):
        return instant(ref, expr, "", format="table")

    return {
        "datasource": PROM,
        "description": (
            "BGP sessions of the fabric: the eBGP underlay to the spines and the "
            "iBGP EVPN overlay between the loopbacks. Routes count every address family."
        ),
        "fieldConfig": {
            "defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto"}, "filterable": False}},
            "overrides": [
                override("Node", {"custom.width": 70}),
                override("Peer AS", {"custom.width": 75}),
                override(
                    "State",
                    {
                        "custom.width": 105,
                        "custom.cellOptions": {"type": "color-text"},
                        "color": {"mode": "fixed", "fixedColor": "orange"},
                        "mappings": BGP_STATE_MAPPING,
                    },
                ),
                override("Up since", {"unit": "dateTimeFromNow", "custom.width": 115}),
                override("Rx", {"custom.width": 50}),
                override("Active", {"custom.width": 60}),
            ],
        },
        "gridPos": G,
        "id": panel_id,
        "options": {
            "cellHeight": "sm",
            "showHeader": True,
            "sortBy": [{"desc": False, "displayName": "Node"}],
        },
        "targets": [
            query("A", f"max by ({keys}) (network_instance_protocols_bgp_neighbor_session_state)"),
            query("B", f"max by ({keys}) (network_instance_protocols_bgp_neighbor_peer_as)"),
            query("C", f"max by ({keys}) (network_instance_protocols_bgp_neighbor_last_established) * 1000"),
            query("D", f"sum by ({keys}) (network_instance_protocols_bgp_neighbor_afi_safi_received_routes)"),
            query("E", f"sum by ({keys}) (network_instance_protocols_bgp_neighbor_afi_safi_active_routes)"),
        ],
        "title": "BGP sessions",
        "transformations": [
            {"id": "merge", "options": {}},
            {
                "id": "organize",
                "options": {
                    "excludeByName": {"Time": True},
                    "indexByName": {
                        "source": 0,
                        "neighbor_peer_address": 1,
                        "Value #B": 2,
                        "Value #A": 3,
                        "Value #C": 4,
                        "Value #D": 5,
                        "Value #E": 6,
                    },
                    "renameByName": {
                        "source": "Node",
                        "neighbor_peer_address": "Neighbor",
                        "Value #B": "Peer AS",
                        "Value #A": "State",
                        "Value #C": "Up since",
                        "Value #D": "Rx",
                        "Value #E": "Active",
                    },
                },
            },
        ],
        "type": "table",
    }


def interface_table(panel_id):
    """One line per selected port with state, rates and error counters."""
    sel = '{source=~"$Node", interface_name=~"$Interface"}'
    by = "max by (source, interface_name, description)"
    queries = [
        ("A", f"{by} (interface_oper_state{sel} {WITH_DESC})", "State"),
        ("B", f"max by (source, interface_name) (interface_mtu{sel})", "MTU"),
        ("C", f"max by (source, interface_name) (interface_traffic_rate_in_bps{sel})", "In"),
        ("D", f"max by (source, interface_name) (interface_traffic_rate_out_bps{sel})", "Out"),
        ("E", f"max by (source, interface_name) (interface_statistics_in_error_packets{sel})", "In errors"),
        ("F", f"max by (source, interface_name) (interface_statistics_out_error_packets{sel})", "Out errors"),
        ("G", f"max by (source, interface_name) (interface_statistics_in_discarded_packets{sel})", "In discards"),
        ("H", f"max by (source, interface_name) (interface_statistics_out_discarded_packets{sel})", "Out discards"),
        ("I", f"max by (source, interface_name) (interface_statistics_carrier_transitions{sel})", "Flaps"),
    ]
    counter = {"custom.cellOptions": {"type": "color-text"}, "color": {"mode": "thresholds"},
               "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}, {"color": "red", "value": 1}]}}
    return {
        "datasource": PROM,
        "description": "Cabled ports of the selected switches. Error and discard counters count since boot.",
        "fieldConfig": {
            "defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto"}}},
            "overrides": [
                override("Node", {"custom.width": 80}),
                override("Port", {"custom.width": 70}),
                override("Connects to", {"custom.width": 110}),
                override("State", {"custom.width": 80, "custom.cellOptions": {"type": "color-background", "mode": "basic"},
                                   "mappings": STATE_MAPPING, "color": {"mode": "thresholds"}, "thresholds": STATE_THRESHOLDS}),
                override("In", {"unit": "bps", "decimals": 1}),
                override("Out", {"unit": "bps", "decimals": 1}),
                *[override(name, counter) for name in ("In errors", "Out errors", "In discards", "Out discards")],
            ],
        },
        "gridPos": G,
        "id": panel_id,
        "options": {"cellHeight": "sm", "showHeader": True, "sortBy": [{"desc": False, "displayName": "Node"}]},
        "targets": [instant(ref, expr, "", format="table") for ref, expr, _ in queries],
        "title": "Ports",
        "transformations": [
            {"id": "merge", "options": {}},
            {
                "id": "organize",
                "options": {
                    "excludeByName": {"Time": True},
                    "indexByName": {"source": 0, "interface_name": 1, "description": 2, **{f"Value #{ref}": i + 3 for i, (ref, _, _) in enumerate(queries)}},
                    "renameByName": {"source": "Node", "interface_name": "Port", "description": "Connects to", **{f"Value #{ref}": name for ref, _, name in queries}},
                },
            },
            # Only the cabled ports: the state query is limited to them.
            {"id": "filterByValue", "options": {"filters": [{"config": {"id": "isNull", "options": {}}, "fieldName": "State"}], "match": "any", "type": "exclude"}},
        ],
        "type": "table",
    }


kpis = [
    stat(
        40,
        "BGP sessions",
        G,
        [
            instant("A", f"count(network_instance_protocols_bgp_neighbor_session_state == {ESTABLISHED}) or vector(0)", "Established"),
            instant("B", "sum(srl:bgp:sessions_down) or vector(0)", "Down"),
        ],
        {**PLAIN, "noValue": "0"},
        "BGP sessions across the fabric, underlay and overlay.",
        overrides=[
            {"matcher": {"id": "byName", "options": "Established"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}}]},
            {"matcher": {"id": "byName", "options": "Down"}, "properties": [{"id": "thresholds", "value": ALERT_IF_ANY["thresholds"]}]},
        ],
    ),
    stat(
        41,
        "Fabric ports",
        G,
        [
            instant("A", f"count(interface_oper_state == 1 {IN_USE}) or vector(0)", "Up"),
            instant("B", "sum(srl:interface:down) or vector(0)", "Down"),
        ],
        {**PLAIN, "noValue": "0"},
        "Oper-state of the cabled ports of all switches.",
        overrides=[
            {"matcher": {"id": "byName", "options": "Up"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}}]},
            {"matcher": {"id": "byName", "options": "Down"}, "properties": [{"id": "thresholds", "value": ALERT_IF_ANY["thresholds"]}]},
        ],
    ),
    stat(
        42,
        "Client traffic",
        G,
        [target("A", 'sum(interface_traffic_rate_in_bps{source=~"leaf.*", interface_name="e1-1"})', "Into the fabric")],
        {"color": {"mode": "fixed", "fixedColor": "blue"}, "mappings": [], "unit": "bps", "decimals": 1, "min": 0},
        "Traffic the clients send into the fabric. Start it with traffic.sh.",
        graphMode="area",
        textMode="value",
    ),
    stat(
        43,
        "EVPN MAC addresses",
        G,
        [
            instant("A", 'sum(network_instance_bridge_table_statistics_mac_type_active_entries{mac_type_type="learnt"}) or vector(0)', "Local"),
            instant("B", 'sum(network_instance_bridge_table_statistics_mac_type_active_entries{mac_type_type="evpn"}) or vector(0)', "Via EVPN"),
        ],
        PLAIN,
        "MAC addresses in the MAC-VRFs of the leaves: learnt on a local port, or received in EVPN routes.",
    ),
    stat(
        44,
        "Warnings",
        G,
        [
            target(
                "A",
                f'sum(count_over_time({{job="syslog", {EVENTS}, {WARNING_LEVELS}}}[$__range])) or vector(0)',
                "Warnings and errors",
                ds=LOKI,
                queryType="instant",
                range=False,
                instant=True,
            )
        ],
        {
            "color": {"mode": "thresholds"},
            "mappings": [],
            "noValue": "0",
            "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 1}]},
        },
        "SR Linux events of severity warning or worse in the selected time range, such as a port or BGP session going down. Debug traces are not counted. See the Logs tab.",
        ds=LOKI,
        textMode="value",
    ),
    stat(
        45,
        "SR Linux",
        G,
        [
            instant(
                "A",
                'count by (release) (label_replace(system_information_version, "release", "$1", "version", "(v[0-9.]+).*"))',
                "{{release}}",
            )
        ],
        {**PLAIN, "unit": "none"},
        "Software release of the switches, with the number of switches that run it.",
        textMode="value_and_name",
    ),
]

fabric_throughput = timeseries(
    1,
    "Fabric throughput",
    G,
    [
        target("A", f"interface_traffic_rate_in_bps {WITH_DESC}", "{{source}} {{interface_name}} in ({{description}})"),
        target("B", f"interface_traffic_rate_out_bps {WITH_DESC}", "{{source}} {{interface_name}} out ({{description}})"),
    ],
    "Traffic rate of the cabled ports of all switches. " + MARKERS,
)

node_panels = [
    timeseries(
        11,
        "Throughput",
        G,
        [
            target("A", f'interface_traffic_rate_in_bps{{source="$Node"}} {WITH_DESC}', "{{interface_name}} in ({{description}})"),
            target("B", f'interface_traffic_rate_out_bps{{source="$Node"}} {WITH_DESC}', "{{interface_name}} out ({{description}})"),
        ],
        "Traffic rate of the cabled ports, as measured by SR Linux. " + MARKERS,
        legend="bottom",
    ),
    stat(
        12,
        "BGP",
        G,
        [
            target("A", 'network_instance_protocols_bgp_statistics_up_peers{source="$Node", network_instance_name="default"}', "Up peers"),
            target("B", 'network_instance_protocols_bgp_statistics_total_peers{source="$Node", network_instance_name="default"}', "Total peers"),
            target("C", 'network_instance_protocols_bgp_statistics_total_received_routes{source="$Node", network_instance_name="default"}', "Rx routes"),
            target("D", 'network_instance_protocols_bgp_statistics_total_active_routes{source="$Node", network_instance_name="default"}', "Active routes"),
        ],
        PLAIN,
        "BGP statistics of the default network instance.",
        orientation="horizontal",
        justifyMode="auto",
        text={"titleSize": 13, "valueSize": 18},
    ),
    stat(
        13,
        "Routes and MACs",
        G,
        [
            target("A", 'network_instance_route_table_ipv4_unicast_statistics_active_routes{source="$Node", network_instance_name="default"}', "IPv4 routes"),
            target("B", 'network_instance_route_table_ipv4_unicast_statistics_active_routes_with_ecmp{source="$Node", network_instance_name="default"}', "ECMP routes"),
            target("C", 'sum(network_instance_bridge_table_statistics_active_entries{source="$Node"}) or vector(0)', "MAC entries"),
        ],
        PLAIN,
        "Active routes of the default network instance, of which ECMP routes, and MAC addresses across all MAC-VRFs.",
        orientation="horizontal",
        justifyMode="auto",
        text={"titleSize": 13, "valueSize": 18},
    ),
    stat(
        14,
        "Net instances",
        G,
        [target("A", 'network_instance_oper_state{source="$Node"}', "{{network_instance_name}}")],
        {"color": {"mode": "thresholds"}, "mappings": STATE_MAPPING, "thresholds": STATE_THRESHOLDS},
        colorMode="background",
        orientation="horizontal",
        text={"titleSize": 12, "valueSize": 14},
    ),
    stat(
        15,
        "Ports",
        G,
        [target("A", f'interface_oper_state{{source="$Node"}} {WITH_DESC}', "{{interface_name}} {{description}}")],
        {"color": {"mode": "thresholds"}, "mappings": STATE_MAPPING, "thresholds": STATE_THRESHOLDS},
        "Oper-state of the cabled ports.",
        colorMode="background",
        orientation="horizontal",
        text={"titleSize": 12, "valueSize": 14},
    ),
    stat(
        16,
        "Release",
        G,
        [instant("A", 'label_replace(system_information_version{source="$Node"}, "release", "$1", "version", "(v[0-9.]+).*")', "{{release}}")],
        PLAIN,
        "",
        textMode="name",
    ),
    stat(
        17,
        "Booted",
        G,
        [target("A", 'system_information_last_booted{source="$Node"} * 1000', "__auto")],
        {**PLAIN, "unit": "dateTimeFromNow"},
        textMode="value",
    ),
    stat(
        18,
        "Last commit",
        G,
        [target("A", 'system_configuration_last_change{source="$Node"} * 1000', "__auto")],
        {**PLAIN, "unit": "dateTimeFromNow"},
        "Time of the last configuration commit. Change the configuration over gNMI or the CLI and watch it update.",
        textMode="value",
    ),
    gauge(19, "CPU", G, 'platform_control_cpu_total_instant{source="$Node"}'),
    gauge(20, "Memory", G, 'platform_control_memory_utilization{source="$Node"}'),
]

PORT_SEL = 'source=~"$Node", interface_name=~"$Interface"'
interface_panels = [
    timeseries(
        50,
        "Traffic rate",
        G,
        [
            target("A", f"interface_traffic_rate_in_bps{{{PORT_SEL}}} {WITH_DESC}", "{{source}} {{interface_name}} in ({{description}})"),
            target("B", f"interface_traffic_rate_out_bps{{{PORT_SEL}}} {WITH_DESC}", "{{source}} {{interface_name}} out ({{description}})"),
        ],
        "Traffic rate of the selected ports. " + MARKERS,
    ),
    timeseries(
        51,
        "Packets",
        G,
        [
            target("A", f"rate(interface_statistics_in_packets{{{PORT_SEL}}}[$__rate_interval]) {WITH_DESC}", "{{source}} {{interface_name}} in ({{description}})"),
            target("B", f"rate(interface_statistics_out_packets{{{PORT_SEL}}}[$__rate_interval]) {WITH_DESC}", "{{source}} {{interface_name}} out ({{description}})"),
        ],
        "Packets per second of the selected ports.",
        unit="pps",
        legend="bottom",
    ),
    timeseries(
        52,
        "Errors and discards",
        G,
        [
            target(ref, f"rate(interface_statistics_{metric}_packets{{{PORT_SEL}}}[$__rate_interval]) {IN_USE}", f"{{{{source}}}} {{{{interface_name}}}} {label}")
            for ref, metric, label in (
                ("A", "in_error", "in errors"),
                ("B", "out_error", "out errors"),
                ("C", "in_discarded", "in discards"),
                ("D", "out_discarded", "out discards"),
            )
        ],
        "Error and discarded packets per second of the selected ports. Flat at zero in a healthy fabric.",
        unit="pps",
        legend="bottom",
    ),
    interface_table(53),
]

LOG_SELECTOR = '{job="syslog", source=~"$Node", application=~"$Application", kind=~"$Kind"}'
SEVERITY_COLOURS = {
    "emerg": "dark-red",
    "alert": "dark-red",
    "crit": "red",
    "err": "red",
    "error": "red",
    "warning": "orange",
    "notice": "blue",
    "informational": "green",
    "info": "green",
    "debug": "purple",
}

log_panels = [
    {
        "datasource": LOKI,
        "description": "Syslog messages per severity.",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "bars",
                    "fillOpacity": 70,
                    "lineWidth": 1,
                    "showPoints": "never",
                    "stacking": {"group": "A", "mode": "normal"},
                    "axisBorderShow": False,
                    "barAlignment": 0,
                },
                "min": 0,
                "unit": "short",
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": level},
                    "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}],
                }
                for level, colour in SEVERITY_COLOURS.items()
            ],
        },
        "gridPos": G,
        "id": 31,
        "interval": "30s",
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            target("A", f"sum by (level) (count_over_time({LOG_SELECTOR} [$__interval]))", "{{level}}", ds=LOKI, queryType="range")
        ],
        "title": "Log volume",
        "type": "timeseries",
    },
    {
        "datasource": LOKI,
        "description": "Syslog messages of the selected switches and applications.",
        "gridPos": G,
        "id": 33,
        "options": {
            "dedupStrategy": "none",
            "enableInfiniteScrolling": True,
            "enableLogDetails": True,
            "prettifyLogMessage": False,
            "showCommonLabels": False,
            "showLabels": True,
            "showTime": True,
            "sortOrder": "Descending",
            "wrapLogMessage": True,
        },
        "targets": [target("A", LOG_SELECTOR, "", ds=LOKI, queryType="range")],
        "title": "Logs",
        "type": "logs",
    },
]

# --- EVPN overlay ----------------------------------------------------------------
MAC = 'network_instance_bridge_table_mac_table_mac_type{source=~"$Node"}'
RIB = "network_instance_bgp_rib_afi_safi_evpn_rib_in_out_rib_in_post"


def points_to(expr):
    """Readable target of a MAC address: the remote leaf, or the local port."""
    expr = vtep_to_leaf(expr, "destination", "points_to")
    return f'label_replace({expr}, "points_to", "local port e$1-$2", "destination", "ethernet-(\\\\d+)/(\\\\d+)\\\\..*")'


mac_table = {
    "datasource": PROM,
    "description": (
        "MAC addresses in the MAC-VRFs of the selected leaves. A learnt MAC sits behind a local port, "
        "an EVPN MAC behind the VTEP of another leaf, which advertised it in an EVPN type 2 route."
    ),
    "fieldConfig": {
        "defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto"}}},
        "overrides": [
            override("Leaf", {"custom.width": 70}),
            override("MAC-VRF", {"custom.width": 80}),
            override("Type", {"custom.width": 75, "custom.cellOptions": {"type": "color-text"},
                              "color": {"mode": "fixed", "fixedColor": "text"},
                              "mappings": [{"options": {"learnt": {"color": "green", "index": 0}, "evpn": {"color": "blue", "index": 1}}, "type": "value"}]}),
        ],
    },
    "gridPos": G,
    "id": 70,
    "options": {"cellHeight": "sm", "showHeader": True, "sortBy": [{"desc": False, "displayName": "MAC address"}]},
    "targets": [instant("A", f"max by (source, network_instance_name, mac_address, mac_type, points_to) ({points_to(MAC)})", "", format="table")],
    "title": "MAC table",
    "transformations": [
        {
            "id": "organize",
            "options": {
                "excludeByName": {"Time": True, "Value": True},
                "indexByName": {"source": 0, "network_instance_name": 1, "mac_address": 2, "mac_type": 3, "points_to": 4},
                "renameByName": {"source": "Leaf", "network_instance_name": "MAC-VRF", "mac_address": "MAC address", "mac_type": "Type", "points_to": "Points to"},
            },
        },
    ],
    "type": "table",
}


def evpn_routes(panel_id):
    by = "count by (source)"
    queries = [
        ("A", f'{by} ({RIB}_mac_ip_route_used_route{{source=~"$Node"}})', "Type 2 received"),
        ("B", f'{by} ({RIB}_mac_ip_route_used_route{{source=~"$Node"}} == 1)', "Type 2 used"),
        ("C", f'{by} ({RIB}_imet_route_used_route{{source=~"$Node"}})', "Type 3 received"),
        ("D", f'{by} ({RIB}_imet_route_used_route{{source=~"$Node"}} == 1)', "Type 3 used"),
    ]
    return {
        "datasource": PROM,
        "description": (
            "EVPN routes per switch. Type 2 (MAC/IP) routes advertise MAC addresses, type 3 (inclusive "
            "multicast) routes the VTEPs that take part in a MAC-VRF. The spines reflect the routes of each "
            "leaf to the others without using them; the leaves receive every route from both spines and use one copy."
        ),
        "fieldConfig": {"defaults": {"custom": {"align": "left", "cellOptions": {"type": "auto"}}, "noValue": "0"}, "overrides": [override("Node", {"custom.width": 70})]},
        "gridPos": G,
        "id": panel_id,
        "options": {"cellHeight": "sm", "showHeader": True, "sortBy": [{"desc": False, "displayName": "Node"}]},
        "targets": [instant(ref, expr, "", format="table") for ref, expr, _ in queries],
        "title": "EVPN routes",
        "transformations": [
            {"id": "merge", "options": {}},
            {
                "id": "organize",
                "options": {
                    "excludeByName": {"Time": True},
                    "indexByName": {"source": 0, **{f"Value #{ref}": i + 1 for i, (ref, _, _) in enumerate(queries)}},
                    "renameByName": {"source": "Node", **{f"Value #{ref}": name for ref, _, name in queries}},
                },
            },
        ],
        "type": "table",
    }


mac_counts = {
    "datasource": PROM,
    "description": "MAC addresses per leaf: learnt on a local port or received over EVPN.",
    "fieldConfig": {
        "defaults": {"color": {"mode": "fixed", "fixedColor": "blue"}, "min": 0, "unit": "none", "decimals": 0},
        "overrides": [
            {"matcher": {"id": "byRegexp", "options": ".*learnt"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}}]},
        ],
    },
    "gridPos": G,
    "id": 72,
    "options": {
        "displayMode": "basic",
        "legend": {"showLegend": False},
        "maxVizHeight": 24,
        "minVizHeight": 14,
        "namePlacement": "left",
        "orientation": "horizontal",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "showUnfilled": True,
        "sizing": "manual",
        "valueMode": "text",
    },
    "targets": [target("A", f"count by (source, mac_type) ({MAC})", "{{source}} {{mac_type}}")],
    "title": "MAC addresses",
    "type": "bargauge",
}


def vtep_rate(ref, direction):
    expr = f'rate(tunnel_vxlan_tunnel_vtep_statistics_{direction}_octets{{source=~"$Node"}}[$__rate_interval]) * 8'
    arrow = "from" if direction == "in" else "to"
    return target(ref, vtep_to_leaf(expr, "vtep_address", "remote"), f"{{{{source}}}} {arrow} {{{{remote}}}}")


vxlan_traffic = timeseries(
    73,
    "VXLAN traffic per remote VTEP",
    G,
    [vtep_rate("A", "in"), vtep_rate("B", "out")],
    MARKERS + " Traffic each leaf exchanges with the other leaves over VXLAN, counted per remote VTEP. "
    "Needs tunnel vxlan-tunnel statistics enabled, as in the startup configuration of the leaves.",
)

alert_list = stat(
    46,
    "Alerts",
    G,
    [
        instant("A", 'count by (alertname) (ALERTS{alertstate="firing"})', "{{alertname}}"),
        instant("B", 'count by (alertname) (ALERTS{alertstate="pending"})', "{{alertname}} (pending)"),
    ],
    {
        # "None" in green, the number of firing alerts in red
        "color": {"mode": "thresholds"},
        "mappings": [],
        "noValue": "None",
        "thresholds": ALERT_IF_ANY["thresholds"],
    },
    "Alerts of the lab and how many switches or ports they fire for: BGPSessionDown, PortDown, "
    "PortErrors and HighCPU. The rules are in configs/prometheus/rules.yml; "
    "Alerting > Alert rules lists them with their state.",
    overrides=[
        {"matcher": {"id": "byRegexp", "options": ".*pending.*"}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}]},
    ],
    orientation="horizontal",
    justifyMode="auto",
    text={"titleSize": 13, "valueSize": 18},
)


def kind_buttons(panel_id):
    """Switch between SR Linux events only and events plus debug traces."""
    return {
        "description": "Show SR Linux events only, or the debug traces of its applications too.",
        "gridPos": G,
        "id": panel_id,
        "options": {
            "displayMode": "button",
            "variable": "Kind",
            "padding": 4,
            "showLabel": True,
            "labelWidth": 10,
            "emptyValue": False,
            "persistent": False,
            "showResetButton": False,
        },
        "targets": [],
        "title": "",
        "transparent": True,
        "type": "volkovlabs-variable-panel",
    }


panels = [
    *[kpi for kpi in kpis if kpi["id"] != 45],
    alert_list,
    fabric_throughput,
    front_panel,
    flow,
    bgp_table(4),
    *node_panels,
    *interface_panels,
    *log_panels,
    switch_buttons(60, "Pick the switches to show. A red outline marks a switch with a BGP session or a cabled port down."),
    port_tree,
    app_tree,
    switch_buttons(63, "Pick the switches whose logs to show."),
    kind_buttons(65),
    switch_buttons(64, "Pick the switches to show. Only the leaves run EVPN."),
    mac_table,
    evpn_routes(71),
    mac_counts,
    vxlan_traffic,
]

variables = [
    {
        "allValue": ".+",
        "current": {"text": ["All"], "value": ["$__all"]},
        "datasource": PROM,
        "definition": "label_values(interface_oper_state,source)",
        "hide": 2,
        "includeAll": True,
        "label": "Switch",
        "multi": True,
        "name": "Node",
        "options": [],
        "query": {
            "qryType": 1,
            "query": "label_values(interface_oper_state,source)",
            "refId": "PrometheusVariableQueryEditor-VariableQuery",
        },
        "refresh": 2,
        "regex": "",
        "sort": 1,
        "type": "query",
    },
    {
        "allValue": ".+",
        "current": {"text": ["All"], "value": ["$__all"]},
        "datasource": PROM,
        "definition": "label_values(interface_oper_state,interface_name)",
        "hide": 2,
        "includeAll": True,
        "label": "Port",
        "multi": True,
        "name": "Interface",
        "options": [],
        "query": {
            "qryType": 1,
            "query": "label_values(interface_oper_state,interface_name)",
            "refId": "PrometheusVariableQueryEditor-VariableQuery",
        },
        "refresh": 2,
        "regex": "",
        "sort": 3,
        "type": "query",
    },
    {
        "allValue": ".+",
        "current": {"text": ["All"], "value": ["$__all"]},
        "datasource": LOKI,
        "definition": "",
        "hide": 2,
        "includeAll": True,
        "label": "Application",
        "multi": True,
        "name": "Application",
        "options": [],
        "query": {"label": "application", "refId": "LokiVariableQueryEditor-VariableQuery", "stream": "", "type": 1},
        "refresh": 2,
        "regex": "",
        "sort": 1,
        "type": "query",
    },
    {
        "current": {"text": "Events", "value": "event"},
        "hide": 2,
        "includeAll": False,
        "label": "Messages",
        "multi": False,
        "name": "Kind",
        "options": [
            {"selected": True, "text": "Events", "value": "event"},
            {"selected": False, "text": "Events and traces", "value": ".*"},
        ],
        "query": "Events : event,Events and traces : .*",
        "type": "custom",
    },
]


def log_annotation(name, colour, events, title):
    expr = f'{{job="syslog", kind="event", source=~"$Node", event=~"{events}"}}'
    return {
        "datasource": LOKI,
        "enable": True,
        "expr": expr,
        # Always on, without a switch in the dashboard controls: the panel
        # descriptions explain the markers.
        "hide": True,
        "iconColor": colour,
        "name": name,
        "tagKeys": "source,event",
        "target": {"expr": expr, "refId": "Anno"},
        "titleFormat": title,
    }


# Marks on the time series where something changed in the fabric, taken from
# the SR Linux events in the logs. Hovering a marker shows the event.
annotations = [
    log_annotation("Port up/down", "orange", "portUp|portDown", "{{source}}: port {{event}}"),
    log_annotation("BGP", "red", "bgpNeighborEstablished|bgpNeighborBackwardTransition", "{{source}}: {{event}}"),
    log_annotation("Commits", "blue", "commitSucceeded", "{{source}}: configuration committed"),
]

UID = "ce11ch1funwu8d"
TITLE = "SR Linux Telemetry"
v1_dashboard = {
    "annotations": {"list": annotations},
    "description": (
        "Nokia SR Linux streaming telemetry lab: gNMI telemetry collected by gnmic into "
        "Prometheus, syslog collected by Alloy into Loki."
    ),
    "editable": True,
    "graphTooltip": 1,
    "links": [
        {
            "icon": "external link",
            "targetBlank": True,
            "title": "Lab on GitHub",
            "type": "link",
            "url": "https://github.com/srl-labs/srl-telemetry-lab",
        }
    ],
    "panels": panels,
    "refresh": "5s",
    "schemaVersion": 41,
    "tags": ["gnmi", "srlinux", "telemetry"],
    "templating": {"list": variables},
    "time": {"from": "now-15m", "to": "now"},
    "timepicker": {},
    "timezone": "",
    "title": TITLE,
    "version": 1,
}

# --- conversion to a v2 dashboard with tabs ------------------------------------
# Grafana converts the panels and variables; the layout is written here.
import urllib.request

STAGING_UID = "srl-telemetry-build"


def api(method, path, body=None):
    request = urllib.request.Request(
        GRAFANA + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"{}")


api("POST", "/api/dashboards/db", {"dashboard": {**v1_dashboard, "uid": STAGING_UID, "title": "build staging"}, "overwrite": True})
converted = api("GET", f"/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/{STAGING_UID}")
api("DELETE", f"/api/dashboards/uid/{STAGING_UID}")
assert not converted["status"]["conversion"]["failed"], converted["status"]
spec = converted["spec"]
elements = spec["elements"]


def item(panel_id, x, y, w, h):
    name = f"panel-{panel_id}"
    assert name in elements, name
    return {"kind": "GridLayoutItem", "spec": {"x": x, "y": y, "width": w, "height": h, "element": {"kind": "ElementReference", "name": name}}}


def grid(*items):
    return {"kind": "GridLayout", "spec": {"items": list(items)}}


def row(title, layout, **extra):
    return {"kind": "RowsLayoutRow", "spec": {"title": title, "collapse": False, "layout": layout, **extra}}


def tab(title, layout):
    return {"kind": "TabsLayoutTab", "spec": {"title": title, "layout": layout}}


fabric = grid(
    item(40, 0, 0, 4, 4),
    item(41, 4, 0, 4, 4),
    item(42, 8, 0, 4, 4),
    item(43, 12, 0, 4, 4),
    item(44, 16, 0, 3, 4),
    item(46, 19, 0, 5, 4),
    item(2, 0, 4, 12, 18),
    item(3, 12, 4, 12, 18),
    item(1, 0, 22, 14, 12),
    item(4, 14, 22, 10, 12),
)

switches = {
    "kind": "RowsLayout",
    "spec": {
        "rows": [
            row("", grid(item(60, 0, 0, 24, 2)), hideHeader=True),
            row(
                "$Node",
                grid(
                    item(11, 0, 0, 10, 10),
                    item(12, 10, 0, 4, 5),
                    item(13, 14, 0, 4, 5),
                    item(14, 18, 0, 3, 5),
                    item(15, 21, 0, 3, 5),
                    item(16, 10, 5, 2, 5),
                    item(17, 12, 5, 3, 5),
                    item(18, 15, 5, 3, 5),
                    item(19, 18, 5, 3, 5),
                    item(20, 21, 5, 3, 5),
                ),
                repeat={"mode": "variable", "value": "Node"},
            ),
        ]
    },
}

interfaces = grid(
    item(61, 0, 0, 5, 28),
    item(50, 5, 0, 19, 9),
    item(51, 5, 9, 10, 9),
    item(52, 15, 9, 9, 9),
    item(53, 5, 18, 19, 10),
)

logs = grid(
    item(62, 0, 0, 5, 26),
    item(63, 5, 0, 13, 2),
    item(65, 18, 0, 6, 2),
    item(31, 5, 2, 19, 7),
    item(33, 5, 9, 19, 17),
)

evpn = grid(
    item(64, 0, 0, 24, 2),
    item(70, 0, 2, 12, 12),
    item(71, 12, 2, 12, 7),
    item(72, 12, 9, 12, 5),
    item(73, 0, 14, 24, 9),
)

layout = {
    "kind": "TabsLayout",
    "spec": {
        "tabs": [
            tab("Fabric", fabric),
            tab("Switches", switches),
            tab("Ports", interfaces),
            tab("EVPN", evpn),
            tab("Logs", logs),
        ]
    },
}

used = {i["spec"]["element"]["name"] for t in (fabric, interfaces, evpn, logs) for i in t["spec"]["items"]}
used |= {i["spec"]["element"]["name"] for r in switches["spec"]["rows"] for i in r["spec"]["layout"]["spec"]["items"]}
assert used == set(elements), set(elements) ^ used

spec["layout"] = layout
spec["title"] = TITLE
# A fresh title for the browser tab, no stale "build staging" anywhere.
dashboard = {
    "apiVersion": "dashboard.grafana.app/v2",
    "kind": "Dashboard",
    "metadata": {"name": UID},
    "spec": spec,
}

with open(out_path, "w") as out:
    json.dump(dashboard, out, indent=2)
    out.write("\n")
print(f"wrote {out_path} with {len(elements)} panels in {len(layout['spec']['tabs'])} tabs")

if flow_dir:
    os.makedirs(flow_dir, exist_ok=True)
    files = {
        "topology.svg": flow["options"]["svg"],
        "topology.yml": flow["options"]["panelConfig"],
        "front-panel.svg": front_svg,
        "front-panel.yml": front_config,
    }
    for name, content in files.items():
        with open(os.path.join(flow_dir, name), "w") as out:
            out.write(content if content.endswith("\n") else content + "\n")
    print(f"wrote {', '.join(files)} to {flow_dir}")
