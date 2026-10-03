# ryu-controller-dos-defense

The project consists of an implementation of a Ryu-based SDN controller for the
detection and mitigation of a DoS attack from a malicious UDP host in a Mininet
network. 

<img width="800" alt="image" src="https://github.com/user-attachments/assets/ad5a37f4-a2f5-4eda-b639-0b9a22d07d26" />

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

Since the controller has a global network view, the host position (`dpid` and `port number`), IP address and maximum associated bandwidth configured in Mininet, are provided to the controller with a text file named `hosts_info.txt`. A possibile feature development is to allow dynamic enumaration of the hosts to be monitored.

The first version of the controller adopts a **K-means based clustering algorithm** for anomaly detection:

<img width="800" alt="image" src="https://github.com/user-attachments/assets/c6adcd56-14ae-40ee-a723-84859c57c367" />

An alarm condition is raised when the instance is closer to the centroid with the highest bandwidth utilization value.

The second version adopts a different anomaly detection algorithm. Starting from the pre-build dataset, it is possible to dynamically add another
500 instances (we call it `window_size`). If the window saturates, the last 500 instances are removed to allow the insertion of new ones.
The algorithm requires the first and the third quartiles Q1 and Q3, of `bandwidth_utilization` feature, to be calculated. This allows the computation of the interquartile range **IQR = Q3 − Q1**.

An instance is classified as an anomaly if its `bandwidth_utilization` value is higher than the calculated **Q3 + 0.25 · IQR**

*The computation of Q3, Q1 and IQR will be affected by the last inserted instances as well as by the pre-built dataset*

**Example:**

The values of Q3, Q1 and IQR are initially calculated on the current instances of the pre-built dataset, and then recomputed after some extra low-load instances, 
within the window size, have been inserted. As expected the value of Q3 decreased.

**Before:**

<img width="500" alt="image" src="https://github.com/user-attachments/assets/1f8634ea-181c-4917-96c0-3524c0ae0499" />

**After:**

<img width="500" alt="image" src="https://github.com/user-attachments/assets/9a211b6b-9af0-41a9-8cbb-36c8e6154ce4" />


As a **Mitigation action** a different approach from simply blocking the port was adopted. According to OpenFlow standard each switch is associated with:
- **Flow table** for rule insertion
- **Meter table** that can have different purposes like forcing a minimum transmission rate beyond which the packets are dropped. 


Meter table is used limit link rate when anomaly detection algorithm raises a possible alarm condition. Packets that exceed the configured rate are dropped. This is an example of **traffic conditioning (policing)**. 

## Complete sytem architecture

<img width="800" alt="image" src="https://github.com/user-attachments/assets/53fb6c5d-cf41-48cd-a155-2420054a7599" />


## Management Layer implementation
The purpose of this section is to present a simplified implementation of the management layer in an SDN environment, based on an easily integrable Python tool
called **Redis**.

<img width="600" alt="image" src="https://github.com/user-attachments/assets/18ea30dd-cdcb-4aeb-946a-8a853008de41" />

It can operate as a **message broker** based on a **publisher/subscriber model**. This is an asynchronous communication system where:
- the publisher sends a message on a channel;
- one or more subscribers listen on that channel;
- all the subscribers receive that message in real time;
- the publisher does not know who the subscribers are, and the subscribers do not
  know the publisher's identity. **They are decoupled**;
- the communication model is unidirectional.

A third thread acting as a subscriber on the channel where the publisher (the external entity) sends the messages was designed. It is called **Listener**. Depending on the received commands, the subscriber acts accordingly.

<img width="600" alt="image" src="https://github.com/user-attachments/assets/4ac97e10-44c6-45ab-bb89-cbd54b6cd0ae" />

<img width="600" alt="image" src="https://github.com/user-attachments/assets/f5deae1c-737f-414c-812e-74aab2dc5d2b" />

Four commands that can be sent through `redis-cli` to Listener task, have been defined :
- block_ip,indirizzo_ip,priority_rule,timeout
- unblock_ip,indirizzo_ip,priority_rule”
- read_log_anomalies
- clean_log_anomalies

## Testing

1) First version with anomaly dection algorithm based on clustering algorithm described previuosly:

Two different traffic conditions are shown in this section:
- when no anomaly is detected. 
- when anomaly is detected by controller, because of large UDP traffic generated by malicious host, and mitigation action is performed. 

**First case**, legitimate traffic generated by each host:

<img width="800" alt="image" src="https://github.com/user-attachments/assets/b990f33a-de19-44a0-85fd-6a7def5b38fa" />

**Second case**, malicious host generates large UDP traffic:

<img width="800" alt="image" src="https://github.com/user-attachments/assets/fe2c4026-310d-427d-8c1f-92f91338c4ac" />

Anomaly detection algorithm raises an alarm condition and mitigation action limits traffic rate to 1Mbs:

<img width="800" alt="image" src="https://github.com/user-attachments/assets/b6e0e08f-0da3-4085-b0e9-1c42450da2dd" />

<img width="800" alt="image" src="https://github.com/user-attachments/assets/fb155d3d-5676-4edf-a645-afa34f7d3768" />

- **Red** — UDP traffic
- **Blue** — TCP traffic


2) Second version with anomaly dection algorithm based on the dynamic threashold approach:

<img width="800" alt="image" alt="image" src="https://github.com/user-attachments/assets/24843364-2c8e-41a1-82fc-f78c34079b74" />

<img width="800" alt="image" alt="image" src="https://github.com/user-attachments/assets/fdfade72-51f7-4801-a3a1-dd8cc5e03bb4" />


- **Red** — UDP traffic
- **Blue** — TCP traffic

<img width="800" alt="image" alt="image" src="https://github.com/user-attachments/assets/81f3df43-829e-43ab-a529-96b4041db17b" />


