# ryu-controller-dos-defense

The project consists of an implementation of a Ryu-based SDN controller for the
detection and mitigation of a DoS attack from a malicious UDP host in a Mininet
network. 

The rules followed during the controller design are:
- Avoid using a static threshold approach for detection of DoS attacks. This
solution, despite its simplicity, requires attention on threshold choice
because it can penalize legitimate hosts.
- Avoid simply blocking the switch port affected by DoS attack because it is difficult to choose the timeout value after which the port will be unblocked. Furthermore, this brute-force approach can block other legitimate flows that pass through the same port and doesn't gaurantee an efficient defense since the malicious host may wait for the timeout to expire and attack again.
- Allow an external entity to apply customs rules on the network (e.g. blocking a specific IP flow, requesting controller feedback and so on). This is called **Management layer** in SDN architecture.
- Design SDN controller in a modular way, using Multithreading and IPC


Two solutions are implemented:
- The first uses an anomaly detection mechanism based on the K-Means clustering algorithm.
- The second uses anomaly detection based on a dynamic threshold.

In both cases a dataset of 3000 instances was built, with features obtained using the `OFPPortStatsRequest` Ryu method. Additinal features are derived by adopting a feature engineering approach:
- `bandwidth utilization` : very useful to measure how heavily a link is used. Its bandwidth can be set in Mininet. This feature is calculated as ratio of the sum of transmit and receive throughput to the link bandwidth.
- `bytes_packets_rx_ratio` : ratio that can help to understand whether few big packets or many small packets are being received. 
- `bytes_packets_tx_ratio` : ratio that has the same meaning of the previous feature but in transmission.
- `efficiency` : index that show if a link is used more for transmission than reception

Since the controller has a network view, the host position (dpid and port number), IP address and maximum associated bandwidth configured in Mininet, are provided to the controller with a text file named `hosts_info.txt`. A possibile feature development is to allow dynamic enumaration of the hosts to be monitored.

The first version of the controller adopts a K-means based clustering algorithm for anomaly detection:

<img width="800" alt="image" src="https://github.com/user-attachments/assets/c6adcd56-14ae-40ee-a723-84859c57c367" />

