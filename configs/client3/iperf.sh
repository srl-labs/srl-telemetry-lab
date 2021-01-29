# Start iperf3 server in the background
# with 10 parallel tcp streams, each 2Mbit/s == 64Mbit/s
# using ipv6 interfaces
iperf3 -c 2002::172:17:11:2 -t 10000 -i 10 -p 5202 -B 2002::172:17:33:2 -P 10 -b 2000000 &
