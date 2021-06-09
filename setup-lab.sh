#!/bin/bash
# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

CFG_DIR=./configs

# configure_srl function performs SR Linux configuraion using gnmic client
# since when SRL containers starts it performs some configuration commits, the immediate gNMI Set will fail
# this function implements a loop that will try to have a successful Set retrying every 2s
configure_srl () {
  OUT=$(/usr/local/bin/gnmic -a clab-st-$1 --timeout 30s -u admin -p admin -e json_ietf --skip-verify set --update-path / --update-file $CFG_DIR/fabric/$1.yml 2>&1)
  echo $OUT | grep -q -e '\"operation\": \"UPDATE\"'
  while [ $? -ne 0 ]; do
    sleep 2
    OUT=$(/usr/local/bin/gnmic -a clab-st-$1 --timeout 30s -u admin -p admin -e json_ietf --skip-verify set --update-path / --update-file $CFG_DIR/fabric/$1.yml 2>&1)
    echo $OUT | grep -q -e '\"operation\": \"UPDATE\"'
  done
  # log succesful exec into the log file
  echo $OUT >> telemetry01-lab-setup.log
}

echo "1 Configuring SR Linux fabric" | tee st-lab-setup.log
echo "  1.1 Configuring leaf1" | tee -a st-lab-setup.log
configure_srl "leaf1"
echo "  1.2 Configuring leaf2" | tee -a st-lab-setup.log
configure_srl "leaf2"
echo "  1.3 Configuring leaf3" | tee -a st-lab-setup.log
configure_srl "leaf3"
echo "  1.4 Configuring spine1" | tee -a st-lab-setup.log
configure_srl "spine1"
echo "  1.5 Configuring spine2" | tee -a st-lab-setup.log
configure_srl "spine2"

echo | tee -a st-lab-setup.log
echo "2 Configuring client IPv4/6" | tee -a st-lab-setup.log
echo "  2.1 Configuring client1 IP addressing" | tee -a st-lab-setup.log
docker exec -it clab-st-client1 bash /config/ip.sh
echo "  2.2 Configuring client2 IP addressing" | tee -a st-lab-setup.log
docker exec -it clab-st-client2 bash /config/ip.sh
echo "  2.3 Configuring client3 IP addressing" | tee -a st-lab-setup.log
docker exec -it clab-st-client3 bash /config/ip.sh
echo
echo "Setup finished, check st-lab-setup.log"