# ryu-controller-dos-defense

The project consists of an implementation of a Ryu-based SDN controller for the
detection and mitigation of a DoS attack from a malicious UDP host in a Mininet
network. 
The rules followed during the controller design are:
- Avoid using a static threshold approach for detection of DoS attacks. This
solution, despite its simplicity, requires attention on threshold choice
because it can penalize legitimate hosts.
- Avoid simply blocking the switch door affected by DoS attack because it is difficult to choose the timeout value after which the door will be unblocked. Furthermore, this brute-force approach can block other legitimate flows that pass through the same port and doesn't gaurantee an efficient defense since the malicious host may wait for the timeout to expire and attack again.
- Allow an external entity to apply customs rules on the network (e.g. blocking a specific IP flow, requesting controller feedback and so on). This is called **Management layer** of the SDN architecture.
- Design SDN controller in a modular way, using Multithreading and IPC


