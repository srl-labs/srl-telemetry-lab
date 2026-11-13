#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Breaks and repairs the fabric to see it in the telemetry.
#
# usage: scenario.sh <scenario> [arguments]
#
#   port-down [node] [port]  shut a cabled port, default leaf3 e1-49
#   port-up [node] [port]    bring it back
#   bgp-down [node] [peer]   disable a BGP session, default leaf1 to spine1
#                            in the EVPN overlay (peer 10.0.2.1)
#   bgp-up [node] [peer]     enable it again
#   congest                  send 8 Mbit/s from client2 to client1, the
#                            link from leaf1 to client1 turns red
#   commit [node]            commit a harmless change, default leaf1
#   reset                    undo all of the above, traffic at the normal rate
#   status                   ports and BGP sessions that are not up
#
# Each scenario prints what to look at in Grafana (http://localhost:3000).

set -eu
cd "$(dirname "$0")"

# Use sudo only when the docker socket is not accessible to the user.
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

SWITCHES="leaf1 leaf2 leaf3 spine1 spine2"

usage() {
    sed -n '7,22p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

# Runs SR Linux CLI commands on a switch and commits them.
# usage: srl <node> <command>...
srl() {
    local node=$1
    shift
    printf '%s\n' "$@" "commit now" | $DOCKER exec -i "${node}" sr_cli -e >/dev/null
}

# Ports that are cabled in the topology.
cabled_ports() {
    case "$1" in
        leaf*) echo "ethernet-1/1 ethernet-1/49 ethernet-1/50" ;;
        spine*) echo "ethernet-1/1 ethernet-1/2 ethernet-1/3" ;;
    esac
}

# e1-49 -> ethernet-1/49
port_name() {
    echo "$1" | sed -E 's#^e([0-9]+)-([0-9]+)$#ethernet-\1/\2#'
}

port_down() {
    local node=${1:-leaf3} port=${2:-e1-49}
    srl "${node}" "set / interface $(port_name "${port}") admin-state disable"
    echo "${node} ${port} is down."
    echo "Grafana: the port turns red on the topology and the faceplate, the Fabric ports"
    echo "and BGP sessions figures count it, the PortDown and BGPSessionDown alerts fire,"
    echo "and the traffic moves to the other spine."
}

port_up() {
    local node=${1:-leaf3} port=${2:-e1-49}
    srl "${node}" "set / interface $(port_name "${port}") admin-state enable"
    echo "${node} ${port} is up again."
}

bgp_down() {
    local node=${1:-leaf1} peer=${2:-10.0.2.1}
    srl "${node}" "set / network-instance default protocols bgp neighbor ${peer} admin-state disable"
    echo "The BGP session from ${node} to ${peer} is disabled."
    echo "Grafana: the BGP sessions table and the BGPSessionDown alert show it, a red marker"
    echo "appears on the graphs. EVPN keeps working over the other spine: see the EVPN tab."
}

bgp_up() {
    local node=${1:-leaf1} peer=${2:-10.0.2.1}
    srl "${node}" "set / network-instance default protocols bgp neighbor ${peer} admin-state enable"
    echo "The BGP session from ${node} to ${peer} is enabled again."
}

congest() {
    bash traffic.sh start 1-2 1M
    echo "Grafana: the link from leaf1 to client1 turns red on the topology, client traffic"
    echo "rises to about 10 Mbit/s. Run 'scenario.sh reset' to go back to the normal rate."
}

commit() {
    local node=${1:-leaf1}
    srl "${node}" "set / system information location \"changed by scenario.sh at $(date +%T)\""
    echo "Committed a change on ${node}."
    echo "Grafana: Last commit on the Switches tab updates, a blue marker appears on the graphs."
}

reset() {
    for node in ${SWITCHES}; do
        local commands=()
        for port in $(cabled_ports "${node}"); do
            commands+=("set / interface ${port} admin-state enable")
        done
        for peer in $($DOCKER exec "${node}" sr_cli -d "info flat network-instance default protocols bgp neighbor * admin-state" |
            awk '/admin-state disable/ {print $8}'); do
            commands+=("set / network-instance default protocols bgp neighbor ${peer} admin-state enable")
        done
        srl "${node}" "${commands[@]}"
    done
    echo "All cabled ports and BGP sessions are enabled."
    if bash traffic.sh status | grep -q -- '-b 1M'; then
        bash traffic.sh start 1-2
    fi
}

status() {
    local problems=0
    for node in ${SWITCHES}; do
        for port in $(cabled_ports "${node}"); do
            if ! $DOCKER exec "${node}" sr_cli -d "info flat from state interface ${port} oper-state" | grep -q "oper-state up"; then
                echo "${node}: port ${port} is down"
                problems=$((problems + 1))
            fi
        done
        while read -r peer state; do
            echo "${node}: BGP session to ${peer} is ${state}"
            problems=$((problems + 1))
        done < <($DOCKER exec "${node}" sr_cli -d "info flat from state network-instance default protocols bgp neighbor * session-state" |
            awk '/session-state/ && !/established/ {print $7, $9}')
    done
    if [ "${problems}" -eq 0 ]; then
        echo "All cabled ports are up and all BGP sessions are established."
    fi
    bash traffic.sh status
}

scenario=${1:-}
shift || true
case "${scenario}" in
    port-down) port_down "$@" ;;
    port-up) port_up "$@" ;;
    bgp-down) bgp_down "$@" ;;
    bgp-up) bgp_up "$@" ;;
    congest) congest ;;
    commit) commit "$@" ;;
    reset) reset ;;
    status) status ;;
    *) usage ;;
esac
