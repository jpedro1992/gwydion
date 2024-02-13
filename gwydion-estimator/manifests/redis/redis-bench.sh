#!/bin/bash
# Purpose: Measure latency via redis-cli and place it as
#          an annotation on redis-leader deployment
# Author: Jose Santos
# -------------------------------------------------------------------------                                                                                                            --

# Set time for sleep, default 10 seconds
SLEEP=3
filename='log.txt'

echo "Redis-bench starting..."
echo "Sleep set to $SLEEP seconds"

# Infinite loop with sleep
while true;do
        # show menu
        clear
		    CLIENTS=$(( $RANDOM % 50000 + 10 ))
        SLEEP=$(( $RANDOM % 60 + 1))
		    echo "clients equal to $CLIENTS"
	      redis-benchmark -h 10.96.170.61 -p 6379 -q -n ${CLIENTS} -l
        echo "Sleep for $SLEEP seconds ... "
        sleep ${SLEEP}
done
