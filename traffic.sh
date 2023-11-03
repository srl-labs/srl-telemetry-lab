#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# look for clab files
shopt -s nullglob
clabfiles=(*.clab.yml)


# functions to deal with yml files, 
# shoutout to Stefan Farestam
# https://stackoverflow.com/questions/5014632/how-can-i-parse-a-yaml-file-from-a-linux-shell-script

parse_yaml() {
    local yaml_file=$1
    local prefix=$2
    local s
    local w
    local fs

    s='[[:space:]]*'
    w='[a-zA-Z0-9_.-]*'
    fs="$(echo @ | tr @ '\034')"

    (
        sed -e '/- [^\“]'"[^\']"'.*: /s|\([ ]*\)- \([[:space:]]*\)|\1-\'$'\n''  \1\2|g' |
            sed -ne '/^--/s|--||g; s|\"|\\\"|g; s/[[:space:]]*$//g;' \
                -e 's/\$/\\\$/g' \
                -e "/#.*[\"\']/!s| #.*||g; /^#/s|#.*||g;" \
                -e "s|^\($s\)\($w\)$s:$s\"\(.*\)\"$s\$|\1$fs\2$fs\3|p" \
                -e "s|^\($s\)\($w\)${s}[:-]$s\(.*\)$s\$|\1$fs\2$fs\3|p" |
            awk -F"$fs" '{
            indent = length($1)/2;
            if (length($2) == 0) { conj[indent]="+";} else {conj[indent]="";}
            vname[indent] = $2;
            for (i in vname) {if (i > indent) {delete vname[i]}}
                if (length($3) > 0) {
                    vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
                    printf("%s%s%s%s=(\"%s\")\n", "'"$prefix"'",vn, $2, conj[indent-1], $3);
                }
            }' |
            sed -e 's/_=/+=/g' |
            awk 'BEGIN {
                FS="=";
                OFS="="
            }
            /(-|\.).*=/ {
                gsub("-|\\.", "_", $1)
            }
            { print }'
    ) <"$yaml_file"
}

unset_variables() {
    # Pulls out the variable names and unsets them.
    #shellcheck disable=SC2048,SC2206 #Permit variables without quotes
    local variable_string=($*)
    unset variables
    variables=()
    for variable in "${variable_string[@]}"; do
        tmpvar=$(echo "$variable" | grep '=' | sed 's/=.*//' | sed 's/+.*//')
        variables+=("$tmpvar")
    done
    for variable in "${variables[@]}"; do
        if [ -n "$variable" ]; then
            unset "$variable"
        fi
    done
}

create_variables() {
    local yaml_file="$1"
    local prefix="$2"
    local yaml_string
    yaml_string="$(parse_yaml "$yaml_file" "$prefix")"
    unset_variables "${yaml_string}"
    eval "${yaml_string}"
}

#interact with the clients 

startTraffic1-2() {
    echo "starting traffic between clients 1 and 2"
    docker exec ${nameprefix}client2 bash /config/iperf.sh
}

startTraffic1-3() {
    echo "starting traffic between clients 1 and 3"
    docker exec ${nameprefix}client3 bash /config/iperf.sh
}

startAll() {
    echo "starting traffic on all clients"
    docker exec ${nameprefix}client2 bash /config/iperf.sh
    docker exec ${nameprefix}client3 bash /config/iperf.sh
}

stopTraffic1-2() {
    echo "stopping traffic between clients 1 and 2"
    docker exec ${nameprefix}client2 pkill iperf3
}

stopTraffic1-3() {
    echo "stopping traffic between clients 1 and 3"
    docker exec ${nameprefix}client3 pkill iperf3
}

stopAll() {
    echo "stopping all traffic"
    docker exec ${nameprefix}client2 pkill iperf3
    docker exec ${nameprefix}client3 pkill iperf3
}



#main


if [ -z "${clabfiles}" ] || [ ${#clabfiles[@]} -ne 1 ]; then
  echo "Specify the topoplogy with -t"
  exit
else
  ymlfile=${clabfiles[0]}
fi

while getopts "t:" opts; do
  case ${opts} in
    t)
      ymlfile=${OPTARG}
      ;;  
  esac
done
shift $((OPTIND-1))

if [ -z ${ymlfile} ]; then
  if [ -z "${clabfiles}" ] || [ ${#clabfiles[@]} -ne 1 ]; then
    echo "Specify the topoplogy with -t"
    exit
  else
    ymlfile=${clabfiles[0]}
  fi
fi

if [ -f "${ymlfile}" ]; then
  create_variables ${ymlfile}
  prefix="${prefix//\"}"
  nameprefix=""
  if [ ! -z "${prefix}" ]; then
    nameprefix=${prefix}"-"${name}"-"
  fi
else
  echo "no such topolgy ${ymlfile}"
  exit
fi



if [ -z "$1" ] || [ -z "$2" ] ; then
  echo "Usage:"
  echo "  ./traffic <-t topology.yml> [command] [traffic pattern]"
  echo ""
  echo "  Available options:"
  echo "    -t       Specify the containerlab topology file, defaults to automatic detection"
  echo "  Available commands:"
  echo "    start    Start the traffic"
  echo "    stop     Stop the traffic"
  echo "  Available traffic patterns:"
  echo "    all      Generate traffic between all clients"
  echo "    1-2      Generate traffic between Client 1 and 2"
  echo "    1-3      Generate traffic between Client 1 and 3"
  echo ""
  exit
fi





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



