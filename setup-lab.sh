#!/bin/bash
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
echo
echo "3 Starting iperf" | tee -a st-lab-setup.log
echo "  3.1 Starting iperf server on client1" | tee -a st-lab-setup.log
docker exec -it clab-st-client1 bash /config/iperf.sh
echo "  3.2 Starting iperf client on client2" | tee -a st-lab-setup.log
docker exec -it clab-st-client2 bash /config/iperf.sh
echo
echo "Setup finished, check st-lab-setup.log"


#TODO 
# add a step chown -R 65534:65534 /root/container-lab/lab-examples/telemetry01/prom-data* to set right permissions for prom container to run

# install weathermap
# curl -LO https://github.com/algenty/flowcharting-repository/raw/master/archives/agenty-flowcharting-panel-0.9.0.zip (or wget from container' /var/lib/grafana/plugins)
# unzip agenty-flowcharting-panel-0.9.0.zip