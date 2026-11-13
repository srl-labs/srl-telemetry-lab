# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Sends traffic to client1 with 8 parallel TCP streams over IPv6.
# usage: iperf.sh [rate per stream, default 200K]
# 8 streams x 200 Kbit/s = 1.6 Mbit/s
RATE=${1:-200K}

# Replace traffic that is already running. The iperf3 server on client1
# needs a moment before it accepts the next test.
if pkill iperf3; then
    sleep 2
fi

for attempt in 1 2 3 4 5; do
    nohup iperf3 -c 2002::172:17:0:1 -t 10000 -i 1 -p 5202 -B 2002::172:17:0:3 -P 8 -b "${RATE}" -M 1480 -l 1480 >/tmp/iperf3.log 2>&1 &
    sleep 2
    if pgrep iperf3 >/dev/null; then
        exit 0
    fi
done
echo "client1 does not accept traffic: $(tail -1 /tmp/iperf3.log)" >&2
exit 1
