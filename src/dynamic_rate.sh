#!/bin/bash


xterm -e "iperf -c 10.0.0.3 -u -b 4M -t 30 -p 5001; sleep 1;
	  	iperf -c 10.0.0.3 -u -b 2M -t 30 -p 5001; sleep 1;
	  	iperf -c 10.0.0.3 -u -b 6M -t 30 -p 5001"

