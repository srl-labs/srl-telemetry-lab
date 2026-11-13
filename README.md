# Nokia SR Linux Streaming Telemetry Lab

[![Discord][discord-svg]][discord-url] [![DevPod][devpod-svg]][devpod-url] [![Codespaces][codespaces-svg]][codespaces-url]  
![w212][w212][Learn more](https://containerlab.dev/macos/#devpod) ![w90][w90][Learn more](https://containerlab.dev/manual/codespaces)

[discord-svg]: https://gitlab.com/rdodin/pics/-/wikis/uploads/b822984bc95d77ba92d50109c66c7afe/join-discord-btn.svg
[discord-url]: https://discord.gg/tZvgjQ6PZf
[devpod-svg]: https://gitlab.com/rdodin/pics/-/wikis/uploads/dfc36636ecaa60f3e70340686d5800db/open-in-devpod-btn.svg
[devpod-url]: https://devpod.sh/open#https://github.com/srl-labs/srl-telemetry-lab
[codespaces-svg]: https://gitlab.com/rdodin/pics/-/wikis/uploads/80546a8c7cda8bb14aa799d26f55bd83/run-codespaces-btn.svg
[codespaces-url]: https://codespaces.new/srl-labs/srl-telemetry-lab?quickstart=1&devcontainer_path=.devcontainer%2Fdocker-in-docker%2Fdevcontainer.json
[w212]: https://gitlab.com/rdodin/pics/-/wikis/uploads/718a32dfa2b375cb07bcac50ae32964a/w212h1.svg
[w90]: https://gitlab.com/rdodin/pics/-/wikis/uploads/bf1b8ea28b4528eb1b66567355a13c5c/w90h1.svg

SR Linux has first-class Streaming Telemetry support thanks to [100% YANG coverage](https://learn.srlinux.dev/yang/) of state and config data. The holistic coverage enables SR Linux users to stream **any** data off of the NOS with on-change, sample, or target-defined support. A discrepancy in visibility across APIs is not about SR Linux.

This lab represents a small Clos fabric with [Nokia SR Linux](https://learn.srlinux.dev/) switches running as containers. The lab topology consists of a Clos topology, plus a Streaming Telemetry stack comprised of [gnmic](https://gnmic.openconfig.net), prometheus and grafana applications.

---

![pic1](https://gitlab.com/rdodin/pics/-/wikis/uploads/0784c31d48ec18fd24111ad8d73478b0/image.png)

In addition to the telemetry stack, the lab also includes a modern logging stack comprised of [Grafana Alloy](https://grafana.com/docs/alloy/latest/) and [loki](https://grafana.com/oss/loki/).

Goals of this lab:

1. Demonstrate how a telemetry stack can be incorporated into the containerlab topology file.
2. Explain SR Linux holistic telemetry support.
3. Provide practical configuration examples for the gnmic collector to subscribe to fabric nodes and export metrics to Prometheus TSDB.
4. Introduce advanced Grafana dashboarding with [FlowPlugin](https://grafana.com/grafana/plugins/andrewbmchugh-flow-panel/) plugin rendering port speeds and statuses.
5. Give a sneak peek of the modern logging telemetry stack with Grafana Alloy and Loki to consume Syslog data from SR Linux nodes.

## Deploying the lab

The lab is deployed with the [containerlab](https://containerlab.dev) project, where [`st.clab.yml`](st.clab.yml) file declaratively describes the lab topology.

```bash
# change into the cloned directory
# and execute
containerlab deploy --reconfigure
```

To remove the lab:

```bash
containerlab destroy --cleanup
```

## Accessing the network elements

Once the lab has been deployed, the different SR Linux nodes can be accessed via SSH through their management IP address, given in the summary displayed after the execution of the deploy command. It is also possible to reach those nodes directly via their hostname, defined in the topology file. Linux clients cannot be reached via SSH, as it is not enabled, but it is possible to connect to them with a docker exec command.

```bash
# reach a SR Linux leaf or a spine via SSH
ssh admin@leaf1
ssh admin@spine1

# reach a Linux client via Docker
docker exec -it client1 bash
```

## Fabric configuration

The DC fabric used in this lab consists of three leaves and two spines interconnected as shown in the diagram.

![pic](https://gitlab.com/rdodin/pics/-/wikis/uploads/14c768a04fc30e09b0bf5cf0b57b5b63/image.png)

Leaves and spines use Nokia SR Linux 7220 IXR-D2L and IXR-D3L chassis respectively. Each network element of this topology is equipped with a [startup configuration file](configs/fabric/) that is applied at the node's startup.

Once booted, network nodes will come up with interfaces, underlay protocols and overlay service configured. The fabric is running Layer 2 EVPN service between the leaves.

### Verifying the underlay and overlay status

The underlay network runs eBGP, while iBGP is used for the overlay network. The Layer 2 EVPN service is configured as explained in this comprehensive tutorial: [L2EVPN on Nokia SR Linux](https://learn.srlinux.dev/tutorials/l2evpn/intro/).

By connecting via SSH to one of the leaves, we can verify the status of those BGP sessions.

```
A:leaf1# show network-instance default protocols bgp neighbor
------------------------------------------------------------------------------------------------------------------
BGP neighbor summary for network-instance "default"
Flags: S static, D dynamic, L discovered by LLDP, B BFD enabled, - disabled, * slow

+-----------+---------------+---------------+-------+----------+-------------+--------------+--------------+---------------+
| Net-Inst  |     Peer      |     Group     | Flags | Peer-AS  |   State     |    Uptime    |   AFI/SAFI   | Rx/Active/Tx] |
+===========+===============+===============+=======+==========+=============+==============+==============+===============+
| default   | 10.0.2.1      | iBGP-overlay  | S     | 100      | established | 0d:0h:0m:27s | evpn         | [4/4/2]       |
| default   | 10.0.2.2      | iBGP-overlay  | S     | 100      | established | 0d:0h:0m:28s | evpn         | [4/0/2]       |
| default   | 192.168.11.1  | eBGP          | S     | 201      | established | 0d:0h:0m:34s | ipv4-unicast | [3/3/2]       |
| default   | 192.168.12.1  | eBGP          | S     | 202      | established | 0d:0h:0m:33s | ipv4-unicast | [3/3/4]       |
+-----------+---------------+---------------+-------+----------+-------------+--------------+--------------+---------------+
```

## Telemetry stack

As the lab name suggests, telemetry is at its core. The following telemetry stack is used in this lab:

| Role                | Software                              |
| ------------------- | ------------------------------------- |
| Telemetry collector | [gnmic](https://gnmic.openconfig.net) |
| Time-Series DB      | [prometheus](https://prometheus.io)   |
| Visualization       | [grafana](https://grafana.com)        |

### gnmic

[gnmic](https://gnmic.openconfig.net) is an Openconfig project that allows to subscribe to streaming telemetry data from network devices and export it to a variety of destinations. In this lab, gnmic is used to subscribe to the telemetry data from the fabric nodes and export it to the prometheus time-series database.

The gnmic configuration file - [configs/gnmic/gnmic-config.yml](./configs/gnmic/gnmic-config.yml) - is applied to the gnmic container at the startup and instructs it to subscribe to the telemetry data and export it to the prometheus time-series database. It shows a few practices worth copying:

* **Sample and on-change subscriptions.** Counters and rates are sampled every 5 seconds. States (port oper-state, BGP session state, network instance state, software version) are streamed on-change, so a port going down shows up the moment it happens, with a 10 second heartbeat that keeps the metric alive in Prometheus.
* **Verified TLS.** gnmic checks the certificates of the switches against the CA that containerlab creates for the lab, instead of skipping the verification.
* **Processors.** Prometheus only stores numbers, so a Starlark processor turns timestamps into epoch seconds, `true`/`false` into 1/0, the BGP session state into a number (6 is established) and text such as the software version and the port descriptions into labels.
* **EVPN overlay.** Besides interface, BGP, routing, bridge table and platform statistics, gnmic collects the MAC table of the MAC-VRFs (whether a MAC was learnt on a local port or received over EVPN, and where it points to), the traffic per remote VTEP and the EVPN routes of type 2 and 3.

### Prometheus

[Prometheus](https://prometheus.io) is a popular open-source time-series database. It is used in this lab to store the telemetry data exported by gnmic. The prometheus configuration file - [configs/prometheus/prometheus.yml](configs/prometheus/prometheus.yml) - instructs prometheus to scrape the data from the gnmic collector with a 5s interval.

[configs/prometheus/rules.yml](configs/prometheus/rules.yml) holds the rules:

* Recording rules for what the dashboard and the alerts share: `srl:interface:in_use` marks the cabled ports and carries their description, `srl:switch:problems` counts the BGP sessions and cabled ports that are down per switch.
* Alert rules: `BGPSessionDown`, `PortDown`, `PortErrors` and `HighCPU`. They show in the Prometheus UI under **Alerts**, in Grafana under **Alerting > Alert rules** and on the dashboard. There is no Alertmanager, so nobody is notified.

### Grafana

Grafana is another key component of this lab as it provides the visualisation for the collected telemetry data. Lab's topology file includes grafana node and configuration parameters such as dashboards, datasources and required plugins.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/dashboard-fabric-dark.webp">
  <img alt="Fabric tab of the dashboard" src="images/dashboard-fabric-light.webp">
</picture>

The dashboard provided by this repository is organized in tabs:

| Tab      | Shows                                                                                                                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fabric   | Key figures of the fabric (BGP sessions, ports, client traffic, EVPN MAC addresses, warnings, alerts), a live topology map, the switch faceplates, fabric throughput and every BGP session |
| Switches | One row per selected switch with throughput, BGP, routes and MACs, network instances, ports, release, uptime, last commit, CPU and memory                       |
| Ports    | Traffic, packet, error and discard rates of the selected ports and a table of all cabled ports with what they connect to                                        |
| EVPN     | The MAC table of the leaves, the EVPN routes per switch and the VXLAN traffic per remote VTEP                                                                    |
| Logs     | Log volume per severity and the syslog messages of the selected switches and applications                                                                      |

Switches, ports and applications are picked with the [Business Variable](https://grafana.com/grafana/plugins/volkovlabs-variable-panel/) panel. A red mark next to a switch tells that one of its BGP sessions or cabled ports is down, an orange or red mark next to an application that it logged warnings or errors. The time series show markers where something happened in the fabric, taken from the logs: orange for a port going up or down, red for a BGP session changing state, blue for a configuration commit.

The topology map and the front panel view are powered by the [flow plugin](https://grafana.com/grafana/plugins/andrewbmchugh-flow-panel/), which overlays telemetry data over SVG graphics. Each half of a link is coloured by the traffic rate leaving that end and labelled with it, and the port bubbles and faceplate ports are coloured by their oper-state. The topology panel is generated from the topology file with the Grafana bundle export of the [containerlab](https://containerlab.dev) topology viewer. The SVG graphics and panel configurations of both views are in [configs/grafana/flow_panels](configs/grafana/flow_panels).

The dashboard is generated by [tools/dashboard](tools/dashboard); see its README to change and rebuild it.

### Access details

Using containerlab's ability to expose ports of the containers to the host, the following services are available on the host machine:

* Grafana: <http://localhost:3000>. Anonymous access is enabled; no credentials are required. If you want to act as an admin, use `admin/admin` credentials.
* Prometheus: <http://localhost:9090/graph>

## Logging stack

The logging stack leverages the Alloy->Loki pipeline, where Alloy receives syslog messages, transforms labels, and ships logs to Loki, a log aggregation system.

The logging infrastructure logs every message from SR Linux that is above Info level. SR Linux writes two kinds of messages, and [Alloy](configs/alloy/alloy-config.alloy) tells them apart:

* **Events** report what happened: a port went down, a BGP session changed state, a commit succeeded. They get the labels `kind="event"` and `event` with the name of the event, such as `portDown` or `bgpNeighborEstablished`.
* **Traces** are the debug output of the SR Linux applications and get `kind="trace"`. At boot they come in bursts of thousands, many of them at warning level.

The message prefix (subsystem, module, source location) moves to structured metadata, so the log line is the message itself. The Logs tab shows events by default and can include the traces; the warning figure and the markers on the graphs count events only.

## Topology view

Open [st.clab.yml](st.clab.yml) in the [containerlab VS Code extension](https://containerlab.dev/manual/vsc-extension/) or the containerlab app to see the lab as a diagram with the telemetry and logging pipelines, in the light or the dark theme. The canvas uses the telemetry style: once the lab runs, the port bubbles show the oper-state and the labels on the links the traffic leaving each port. The **Try it** buttons start and stop traffic, shut a port, disable a BGP session, change the configuration of leaf1 and repair everything again, with the scripts described below; their output shows as a notification.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/topology-view-dark.webp">
  <img alt="Topology view with the pipelines and the script buttons" src="images/topology-view-light.webp">
</picture>

## Traffic generation

When the lab is started, there is no traffic running between the nodes. To run traffic between the clients, use the `traffic.sh` control script:

* `bash traffic.sh start all` - start traffic from client2 and client3 to client1
* `bash traffic.sh start 1-2` - start traffic from client2 to client1
* `bash traffic.sh start 1-3` - start traffic from client3 to client1
* `bash traffic.sh start 1-2 1M` - send 8 streams of 1 Mbit/s instead of the default 200 Kbit/s
* `bash traffic.sh stop all` - stop all traffic
* `bash traffic.sh status` - show which clients send traffic

The traffic rate is reflected on the grafana dashboard.

<https://github.com/srl-labs/srl-telemetry-lab/assets/5679861/158914fc-9100-416b-8b0f-cde932895cec>

## Scenarios

`scenario.sh` breaks and repairs the fabric, so you can see it in the telemetry. Start the traffic first, open the dashboard, then try:

| Command | What happens | Where to look |
| --- | --- | --- |
| `bash scenario.sh port-down leaf3 e1-49` | The uplink from leaf3 to spine1 goes down | The port turns red on the topology and the faceplate, the `PortDown` and `BGPSessionDown` alerts fire, the traffic moves to spine2 |
| `bash scenario.sh bgp-down leaf1 10.0.2.1` | The EVPN session from leaf1 to spine1 is disabled | The BGP sessions table, a red marker on the graphs; the EVPN tab shows that the MAC addresses stay, learnt over spine2 |
| `bash scenario.sh congest` | client2 sends 8 Mbit/s to client1 | The access links of leaf1 and leaf2 turn red on the topology |
| `bash scenario.sh commit leaf1` | Changes the configuration of leaf1 and commits it; the change is harmless, it sets the system location | **Last commit** on the Switches tab, a blue marker on the graphs |
| `bash scenario.sh status` | Lists ports and BGP sessions that are not up | |
| `bash scenario.sh reset` | Undoes all of the above | Everything turns green again |

## Smoke test

[tools/smoke-test.mjs](tools/smoke-test.mjs) checks a deployed lab: BGP, telemetry, EVPN data, logs, alerts and every tab of the dashboard. The [smoke test workflow](.github/workflows/smoke-test.yml) runs it on GitHub for every pull request.

```bash
npm ci --prefix tools
npx --prefix tools playwright install chromium
START_TRAFFIC=1 node tools/smoke-test.mjs
```
