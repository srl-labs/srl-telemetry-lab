#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Starts and stops iperf3 traffic from client2 and client3 to client1.
#
# usage: traffic.sh start|stop|status [all|1-2|1-3] [rate]
#
#   rate  rate of each of the 8 TCP streams per client, default 200K
#         (8 x 200 Kbit/s = 1.6 Mbit/s per client)
#
# examples:
#   bash traffic.sh start all       start traffic from client2 and client3
#   bash traffic.sh start 1-2 1M    8 Mbit/s from client2, a link turns red
#   bash traffic.sh stop all
#   bash traffic.sh status

set -eu

# Use sudo only when the docker socket is not accessible to the user.
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

usage() {
    sed -n '7,18p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

clients() {
    case "${1:-all}" in
        all) echo "client2 client3" ;;
        1-2) echo "client2" ;;
        1-3) echo "client3" ;;
        *) usage ;;
    esac
}

start() {
    local rate=${2:-200K}
    for client in $(clients "${1:-all}"); do
        echo "starting traffic from ${client} to client1 at 8 x ${rate}bit/s"
        $DOCKER exec "${client}" bash /config/iperf.sh "${rate}"
    done
}

stop() {
    for client in $(clients "${1:-all}"); do
        echo "stopping traffic from ${client}"
        $DOCKER exec "${client}" pkill iperf3 || true
    done
}

status() {
    for client in client2 client3; do
        if args=$($DOCKER exec "${client}" pgrep -a iperf3 2>/dev/null); then
            echo "${client}: sending ($(echo "${args}" | grep -o -- '-b [^ ]*' | head -1))"
        else
            echo "${client}: idle"
        fi
    done
}

case "${1:-}" in
    start) start "${2:-all}" "${3:-200K}" ;;
    stop) stop "${2:-all}" ;;
    status) status ;;
    *) usage ;;
esac
