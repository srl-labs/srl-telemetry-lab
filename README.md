# SR Linux Streaming Telemetry Lab
SR Linux has first-class Streaming Telemetry support thanks to 100% YANG coverage of state and config data. The wholistic coverage enables SR Linux users to stream **any** data off of the NOS with on-change, sample, or target-defined support. A discrepancy in visibility across APIs is not about SR Linux.

This lab represents a small Clos fabric with SR Linux switches running as containers. The lab setup consists of a fabric itself, plus a Streaming Telemetry stack comprised of gnmic, prometheus and grafana applications.

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
clab dep -t st.clab.yml
```

## Fabric configuration
The DC fabric used in this lab consists of three leaves and two spines interconnected with each other as shown in the diagram.

Leaves and spines use Nokia SR Linux IXR-D2 and IXR-D3L chassis respectively. Each network element of this topology is equipped with a startup configuration file that is applied on node's startup.

## Running traffic
To run traffic between the nodes, leverage `traffic.sh` control script.

## Access details

* Grafana: http://localhost:3000
* Prometheus: http://localhost:9090/graph