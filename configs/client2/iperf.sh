# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Start iperf3 server in the background
# with 32 parallel tcp streams, each 2Mbit/s == 64Mbit/s
# using ipv6 interfaces
iperf3 -c 2002::172:17:11:2 -t 10000 -i 10 -p 5201 -B 2002::172:17:22:2 -P 32 -b 2000000 &
