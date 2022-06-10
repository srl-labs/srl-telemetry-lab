# SR Linux Streaming Telemetry Lab
SR Linux has first-class Streaming Telemetry support thanks to 100% YANG coverage of state and config data. The wholistic coverage enables SR Linux users to stream **any** data off of the NOS with on-change, sample, or target-defined support. A discrepancy in visibility across APIs is not about SR Linux.

This lab represents a small Clos fabric with [Nokia SR Linux](https://learn.srlinux.dev/) switches running as containers. The lab topology consists of a Clos itself, plus a Streaming Telemetry stack comprised of gnmic, prometheus and grafana applications.

![pic1](https://gitlab.com/rdodin/pics/-/wikis/uploads/5a0deb299f40b1b9572d64c73c9890de/image.png)

Goals of this lab:

1. Demonstrate how a telemetry stack can be incorporated into the same clab topology file.
2. Explain SR Linux wholistic telemetry support.
2. Provide practical configuration examples for the gnmic collector to subscribe to fabric nodes and export metrics to Prometheus TSDB.
3. Introduce advanced Grafana dashboarding with FlowChart plugin rendering port speeds and statuses.

## Deploying the lab
The lab is deployed with [containerlab](https://containerlab.dev) project where [`st.clab.yml`](st.clab.yml) file declaratively describes the lab topology.

```bash
# deploy a lab
containerlab deploy -t st.clab.yml
```

## Fabric configuration
The DC fabric used in this lab consists of three leaves and two spines interconnected with each other as shown in the diagram.

![pic](https://gitlab.com/rdodin/pics/-/wikis/uploads/6d7c55ab460cff731ae8652a385877f8/image.png)

Leaves and spines use Nokia SR Linux IXR-D2 and IXR-D3L chassis respectively. Each network element of this topology is equipped with a [startup configuration file](configs/fabric/) that is applied at the node's startup.

Once booted, network nodes will come up with interfaces, underlay protocols and overlay service configured. The fabric is configured with Layer 2 EVPN service between the leaves.

## Running traffic
To run traffic between the nodes, leverage `traffic.sh` control script.

To start the traffic:

* `bash traffic.sh start all` - start traffic between all nodes
* `bash traffic.sh start 1-2` - start traffic between client1 and client2
* `bash traffic.sh start 1-3` - start traffic between client1 and client3

To stop the traffic:

* `bash traffic.sh stop` - stop traffic generation

## Telemetry stack
As the lab name suggests, telemetry is at its core. The following stack of software solutions has been chosen for this lab:

| Role                | Software                            |
| ------------------- | ----------------------------------- |
| Telemetry collector | [gnmic](https://gnmic.kmrd.dev)     |
| Time-Series DB      | [prometheus](https://prometheus.io) |
| Visualization       | [grafana](https://grafana.com)      |

## Grafana
Grafana is a key component of this lab. Lab's topology file includes grafana node along with its configuration parameters such as dashboards, datasources and required plugins.

Grafana dashboard provided by this repository provides multiple views on the collected real-time data. Powered by [flowchart plugin](https://grafana.com/grafana/plugins/agenty-flowcharting-panel/) it overlays telemetry sourced data over graphics such as topology and front panel views:

![pic3](https://gitlab.com/rdodin/pics/-/wikis/uploads/919092da83782779b960eeb4b893fb4a/image.png)

Using the flowchart plugin and real telemetry data users can create interactive topology maps (aka weathermap) with a visual indication of link rate/utilization.

![pic2](https://gitlab.com/rdodin/pics/-/wikis/uploads/12f154dafca1270f7a1628c1ed3ab77a/image.png)

## Access details

* Grafana: http://localhost:3000
* Prometheus: http://localhost:9090/graph