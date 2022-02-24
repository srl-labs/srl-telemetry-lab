# SR Linux Streaming Telemetry Lab
SR Linux has first-class Streaming Telemetry support thanks to 100% YANG coverage of state and config data. The wholistic coverage enables SR Linux users to stream **any** data off of the NOS with on-change, sample, or target-defined support. Discrepancy in visibility across APIs is not about SR Linux.

With the files contained within this repository anyone can spin up a small Clos fabric with SR Linux switches running as containers. The lab setup consists of a fabric itself, plus Streaming Telemetry stack comprised of gnmic, prometheus and grafana applications.

![pic1](https://gitlab.com/rdodin/pics/-/wikis/uploads/5a0deb299f40b1b9572d64c73c9890de/image.png)

## Deploy lab
The lab is defined and deployed with containerlab project. The `st.clab.yml` file declaratively describes the lab setup.

```
clab dep -t st.clab.yml
```

## Configure fabric
Fabric configuration consists of adding SR Linux configuration (interfaces, IGP, BGP) as well as adding interface addressing on the client side.

## Running traffic
To run traffic between the nodes, leverage `traffic.sh` control script.

## Access details
Grafana: http://localhost:3000
Prometheus: http://localhost:9090/graph