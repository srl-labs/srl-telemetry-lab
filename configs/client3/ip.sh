# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Add IPv4
ip address add 172.17.33.2/24 dev eth1
ip route add 172.17.0.0/16 via 172.17.33.1

# Add IPv6
ip -6 address add 2002::172:17:33:2/112 dev eth1
ip -6 route add 2002::172:17:0:0/96 via 2002::172:17:33:1
