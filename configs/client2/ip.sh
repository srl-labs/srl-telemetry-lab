# Copyright 2020 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

# Add IPv4
ip address add 172.17.0.22/24 dev eth1

# Add IPv6
ip -6 address add 2002::172:17:22:2/96 dev eth1
