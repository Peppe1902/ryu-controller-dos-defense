# ryu-controller-dos-defense
Ryu-based SDN controller for real-time DoS attack detection and mitigation

The project consists of an implementation of a Ryu-based SDN controller for the
detection and mitigation of a DoS attack from a malicious UDP host in a Mininet
network.


Scopo di questa sezione e delle successive è quello di mitigare un attacco di tipo Denial of service da parte di un host UDP malevolo in una rete Mininet con l’ausilio di un controller SDN (RYU) adottando un approccio differente rispetto a quello dell’anno scorso cercando di rimuovere alcune limitazioni :
1. L’approccio basato sul calcolo del throughput e confronto di quest’ultimo con una soglia, per quanto semplice, presentava alcune sfide tra cui la scelta della soglia, per evitare di penalizzare inutilmente un altro host legittimo.(Static Threshold)
2. L’eventuale veridicità della condizione di confronto del punto precedente prevedeva di bloccare la porta dello switch interessata entro un certo tempo. Quest’ultima non era una soluzione perfetta, principalmente perchè scegliere il timeout dopo il quale la porta dovrà essere sbloccata è tutt’altro che banale; oltre al fatto che un attaccante potrebbe banalmente attendere quel tempo e procedere nuovamente con i suoi fini malevoli. (Inflexible Blocking/Unblocking Policy)
3. Riallacciandosi al punto precedente, bloccare una intera porta potrebbe essere troppo “brute-force” come approccio, soprattutto se su quella porta sono indirizzati differenti flussi. Quindi quello che è stato fatto è non bloccare l’intera porta, bensì operare sul flusso di pacchetti provenienti da un determinato IP. (Over blocking )
4. Nella realtà non è il solo controller a prendere decisioni sul comportamento della rete ma anche l’organizzazione che detiene il controllo di quella rete. Quindi sarebbe auspicabile che dall’esterno qualcuno possa richiedere dei comportamenti attesi come blocking di un flusso di pacchetti IP, richiesta di eventuali anomalie che il controller ha rilevato e così via… (Controller-Centric Blocking Decisions)
5. Per favorire la semplicità nel testing, il controller SDN è stato definito in maniera modulare grazie al multihreading e alla IPC (inter-process communication) che Python offre.(Lack of Modular Detection and Mitigation Design)
