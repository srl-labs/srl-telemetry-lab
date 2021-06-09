#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause


set -eu

startTraffic1-2() {
    echo "starting traffic between clients 1 and 2"
    docker exec clab-st-client1 bash /config/iperf.sh
    docker exec clab-st-client2 bash /config/iperf.sh
}

startTraffic1-3() {
    echo "starting traffic between clients 1 and 3"
    docker exec clab-st-client1 bash /config/iperf.sh
    docker exec clab-st-client3 bash /config/iperf.sh
}

stopAll() {
    echo "stopping all traffic"
    docker exec clab-st-client1 pkill iperf3
    docker exec clab-st-client2 pkill iperf3
    docker exec clab-st-client3 pkill iperf3
}

startAll() {
    echo "starting traffic on all clients"
    docker exec clab-st-client1 bash /config/iperf.sh
    docker exec clab-st-client2 bash /config/iperf.sh
    docker exec clab-st-client3 bash /config/iperf.sh
}

# start traffic
if [ $1 == "start" ]; then
    if [ $2 == "1-2" ]; then
        startTraffic1-2
    fi
    if [ $2 == "1-3" ]; then
        startTraffic1-3
    fi
    if [ $2 == "all" ]; then
        startAll
    fi
fi

if [ $1 == "stop" ]; then
    if [ $2 == "all" ]; then
        stopAll
    fi
fi