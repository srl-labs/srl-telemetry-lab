#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause


set -eu

startTraffic1-2() {
    echo "starting traffic between clients 1 and 2"
    sudo docker exec client2 bash /config/iperf.sh
}

startTraffic1-3() {
    echo "starting traffic between clients 1 and 3"
    sudo docker exec client3 bash /config/iperf.sh
}

startAll() {
    echo "starting traffic on all clients"
    sudo docker exec client2 bash /config/iperf.sh
    sudo docker exec client3 bash /config/iperf.sh
}

stopTraffic1-2() {
    echo "stopping traffic between clients 1 and 2"
    sudo docker exec client2 pkill iperf3
}

stopTraffic1-3() {
    echo "stopping traffic between clients 1 and 3"
    sudo docker exec client3 pkill iperf3
}

stopAll() {
    echo "stopping all traffic"
    sudo docker exec client2 pkill iperf3
    sudo docker exec client3 pkill iperf3
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
    if [ $2 == "1-2" ]; then
        stopTraffic1-2
    fi
    if [ $2 == "1-3" ]; then
        stopTraffic1-3
    fi
    if [ $2 == "all" ]; then
        stopAll
    fi
fi