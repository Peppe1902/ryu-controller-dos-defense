import time
import threading
import queue
import os
import pandas as pd
from ryu.base import app_manager
import redis
from sklearn.cluster import KMeans
import pandas as pd
import numpy as np
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class Monitor(app_manager.RyuApp) :

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    
    #costruttore
    def __init__(self,*args,**wargs) :
        super(Monitor,self).__init__(*args,**wargs)
        self.name_file = 'dataset.txt'
        self.log_file = 'log_anomalies.txt'
        self.hosts_info = 'hosts_info.txt'
        self.bandwidth_links = {}
        self.init_file()
        self.host_locations = {}
        self.infoHosts()
        print(self.host_locations)
        self.centroids = self.applyClustering()
        #print(self.centroids)
        self.switch_table = {}
        self.datapaths = {}
        self.period = 5 #periodo del thread
        self.old_rx_packets = {}
        self.old_tx_packets = {}
        self.old_rx_bytes = {}
        self.old_tx_bytes = {}
        self.old_rx_packets = {}
        self.old_tx_packets = {}
        self.old_packet_in = {}
        self.throughput_rx_bps = {}
        self.throughput_tx_bps = {}
        self.queue = queue.Queue(maxsize = 5)
        self.lock_file = threading.Lock()
        self.controller_channel_request = "controller_channel"
        self.controller_channel_response = "controller_response"
        self.thread_monitor = threading.Thread(target=self.monitor_ports)
        self.thread_monitor.daemon=True
        self.thread_monitor.start()

        self.threadMitigation = threading.Thread(target = self.limit_flow)
        self.threadMitigation.daemon=True
        self.threadMitigation.start()

        self.redis_client = redis.Redis() 
        self.pubsub = self.redis_client.pubsub() #creo un oggetto pubsub
        self.pubsub.subscribe(self.controller_channel_request) #divento subscriber del canale
    
        self.threadListener= threading.Thread(target = self.listen_channel)
        self.threadListener.daemon=True
        self.threadListener.start()
        
    def init_file(self) :
        if not os.path.exists(self.name_file):
            with open(self.name_file, "w") as f:
                header = "dpid,port_no,delta_rx_packets,delta_rx_bytes,delta_tx_packets,delta_tx_bytes,bytes_packets_rx_ratio,"
                header = header + "bytes_packets_tx_ratio,efficiency,bandwidth_utilization,throughput_tx_bps,throughput_rx_bps\n"
                f.write(header)


    def infoHosts(self) :
        with open(self.hosts_info,'r') as f:
            next(f)
            for line in f :
                fields = line.strip().split(',')
                self.bandwidth_links.setdefault(int(fields[0]),{})
                self.bandwidth_links[int(fields[0])][int(fields[1])] = float(fields[3])
                self.host_locations[str(fields[2])] = (int(fields[0]),int(fields[1]))
        
 
    def applyClustering(self) :
        df = pd.read_csv(self.name_file)

        df = df.drop(df.columns[[0,1]],axis=1)

        #definiamo come centroide quello che è la mediana
        kmeans = KMeans(n_clusters = 3,random_state=0)
        
        kmeans.fit(df)

        return kmeans.cluster_centers_
    

    def controlAnomaly(self,instance): #metodo per il rilevamento di una anomalia in base ad una istanza

        min_distance = np.sqrt(np.sum((instance-self.centroids[0,:])**2))
        index_cluster = 0
    
        for k in range(1,len(self.centroids)) :
            distance = np.sqrt(np.sum((instance-self.centroids[k,:])**2))
            if distance < min_distance :
                index_cluster = k
                min_distance = distance
        
        centroidMax = (0,self.centroids[0])
        
        for k in range(1,len(self.centroids)) :
            if self.centroids[k,7] > centroidMax[1][7]:
                centroidMax = (k,self.centroids[k])

        print('index of cluster = ',index_cluster)
    
        return centroidMax[0] == index_cluster

    def listen_channel(self) :
    
        for message in self.pubsub.listen() :#metto in ascolto di messaggi
            if message['type'] == 'message' :
                command = message['data'].decode() #decodifico i dati ricevuti
                if command.startswith('block_ip') : #comando per bloccare un flusso di pacchetti IP

                    print(("Thread Listener : Received command : %s") %(command))
                    command_info = command.split(',')
                    priority = int(command_info[2])
                    ip = command_info[1]
                    hard_timeout=int(command_info[3])
                    self.redis_client.publish(self.controller_channel_response, f"Bloccato traffico da IP: {ip}")

                    for datapath in self.datapaths.values() : 
                        #ofproto = datapath.ofproto
                        ofp_parser = datapath.ofproto_parser
                        
                        #blocco il flusso di pacchetti con quell'ip sorgente
                        match = ofp_parser.OFPMatch(eth_type = 0x0800,ipv4_src = ip) 
                        actions = []
                        
                        self.add_flow(datapath,match,priority,actions,hard_timeout)

                if command.startswith('unblock_ip') : #comando per sbloccare un flusso di pacchetti IP

                    print(("Thread Listener : Received command : %s") %(command))
                    command_info = command.split(',')
                    ip = command_info[1]
                    priority = int(command_info[2])
                    self.redis_client.publish(self.controller_channel_response, f'Sbloccato traffico da IP: {ip}')

                    for datapath in self.datapaths.values() :
                        #ofproto = datapath.ofproto
                        ofp_parser = datapath.ofproto_parser

                        #sblocco il flusso di pacchetti con quell'ip sorgente
                        match=ofp_parser.OFPMatch(eth_type=0x0800,ipv4_src=ip)

                        self.remove_flow(datapath,match,priority)

                if command.startswith('read_log_anomalies') : #comando per leggere il log delle anomalie
                    print(("Thread Listener : Received command : %s") %(command))
                    with self.lock_file :
                        with open(self.log_file,'r') as f :
                            lines = f.readlines()
                            for line in lines :
                                self.redis_client.publish(self.controller_channel_response,line.strip())
                                #line.strip rimuove caratteri spazio all'inizio alla fine
                       
             
                if command.startswith('clean_log_anomalies') : #comando per svuotare il log delle anomalie
                    print(("Thread Listener : Received command : %s") %(command))
                    with self.lock_file :
                        with open(self.log_file, 'w') as log_f :
                            pass  # Fa nulla, ma apre il file in scrittura, quindi lo svuota
                    

    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER,DEAD_DISPATCHER])
    def state_change_handler(self,ev) :
        datapath=ev.datapath

        if ev.state==MAIN_DISPATCHER :
            if datapath.id not in self.datapaths.keys() :
                self.datapaths[datapath.id] = datapath
        elif ev.state==DEAD_DISPATCHER : #switch disconnesso
            if datapath.id in self.datapaths.keys() :
                del self.datapaths[datapath.id] #rimuovo il datapath corrispondente


    #funzione richiamata dal task di monitoraggio
    def monitor_ports(self) :
        while True :

            msg_list = []
            #devo solo monitorare le porte degli switch che sono direttamente connesse agli hosts
            for dpid,in_port in self.host_locations.values() :
                
                if dpid in self.datapaths.keys() :
                    #ofproto = self.datapaths[dpid].ofproto
                    ofp_parser = self.datapaths[dpid].ofproto_parser
                
                    msg_out = ofp_parser.OFPPortStatsRequest(datapath=self.datapaths[dpid],flags=0,port_no=in_port)
                    msg_list.append((dpid,msg_out))


            for msg in msg_list :
                dpid = msg[0]
                msg_out = msg[1]
                self.datapaths[dpid].send_msg(msg_out)

            time.sleep(self.period)
    

    #gestiamo l'evento di ricezione delle features di uno switch, la fase di negoziazione è 
    #quella di CONFIG
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures,CONFIG_DISPATCHER)
    def switch_features_handler(self,ev) :
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        match = ofp_parser.OFPMatch() #match di qualunque pacchetto 

        actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,ofproto.OFPCML_NO_BUFFER)]

        self.add_flow(datapath,match,0,actions,0)


    #installazione regola nella flow-table
    def add_flow(self,datapath,match,priority,actions,hard_timeout,buffer_id=None) :
        
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        instr = [ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,actions)]

        msgFlow = None
        if buffer_id :
            msgFlow = ofp_parser.OFPFlowMod(datapath=datapath,hard_timeout=hard_timeout,priority=priority,match=match,
                                            instructions=instr,buffer_id=buffer_id)
        else :
            msgFlow = ofp_parser.OFPFlowMod(datapath=datapath,hard_timeout=hard_timeout,priority=priority,match=match,
                                            instructions=instr)
            
        datapath.send_msg(msgFlow)

    def remove_flow(self,datapath,match,priority,buffer_id =None) :
        ofproto = datapath.ofproto 
        ofp_parser = datapath.ofproto_parser

        msg = None
        if buffer_id :
            msg = ofp_parser.OFPFlowMod(datapath=datapath,match=match,buffer_id=buffer_id,command=ofproto.OFPFC_DELETE_STRICT,
                                    priority=priority,out_port = ofproto.OFPP_ANY,out_group=ofproto.OFPG_ANY)
            #OFPFC_DELETE_STRICT elimina la regolaì che matcha perfettamente e con la stessa priorità
        else :
            msg = ofp_parser.OFPFlowMod(datapath=datapath,match=match,command=ofproto.OFPFC_DELETE_STRICT,
                                    priority=priority,out_port = ofproto.OFPP_ANY,out_group=ofproto.OFPG_ANY)
            
        datapath.send_msg(msg)

        
    def limit_flow(self) :
        while True :
            data_queue = self.queue.get(block=True, timeout=None)

            datapath = data_queue[0]
            in_port = data_queue[1]
            malicious_ip = data_queue[2]
            timeout = data_queue[3]

            ofproto = datapath.ofproto 
            ofp_parser = datapath.ofproto_parser
               
            #----------limito il rate del flusso con quell'IP sorgente------------
            match = ofp_parser.OFPMatch(in_port = in_port,eth_type=ether_types.ETH_TYPE_IP ,ipv4_src=malicious_ip)
       
            msg_meter = ofp_parser.OFPMeterMod(datapath=datapath,command = ofproto.OFPMC_ADD,flags=ofproto.OFPMF_KBPS,meter_id=1,
                                       bands=[ofp_parser.OFPMeterBandDrop(rate=1000, burst_size=500)])
            datapath.send_msg(msg_meter)

            actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_NORMAL)] #"lascio che lo switch si comporti normalmente, 
            #come se fosse uno switch L2 tradizionale".

            instr = [ofp_parser.OFPInstructionMeter(meter_id=1),
                 ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,actions)]
        
            msg_flow = ofp_parser.OFPFlowMod(datapath=datapath,command=ofproto.OFPFC_ADD,priority=2,match=match,instructions=instr,
                                         hard_timeout=timeout)
            datapath.send_msg(msg_flow)
        

    @set_ev_cls(ofp_event.EventOFPPortStatsReply,MAIN_DISPATCHER)
    def port_stats_handler(self,ev) :

        #se non è presente l'id di quello switch lo inserisco inizializzandolo ad un default value
        self.old_rx_bytes.setdefault(ev.msg.datapath.id,{})
        self.old_tx_bytes.setdefault(ev.msg.datapath.id,{})
        self.old_rx_packets.setdefault(ev.msg.datapath.id,{})
        self.old_tx_packets.setdefault(ev.msg.datapath.id,{})
        self.throughput_tx_bps.setdefault(ev.msg.datapath.id,{})
        self.throughput_rx_bps.setdefault(ev.msg.datapath.id,{})
    

        ports = []

        body = ev.msg.body

        for stat in body :
            
            dpid = ev.msg.datapath.id
            port_no = stat.port_no

            if port_no == ofproto_v1_3.OFPP_LOCAL :
                continue

            #se non è presente la chaive port_no associata a quello switch inizializzo il valore a 0
            self.old_rx_bytes[dpid].setdefault(port_no,0)
            self.old_tx_bytes[dpid].setdefault(port_no,0)
            self.old_rx_packets[dpid].setdefault(port_no,0)
            self.old_tx_packets[dpid].setdefault(port_no,0)

            #calcolo il throughput come differenza tra new e old e divido per il periodo
            #la moltiplicazione per 8 è per passare a bps
            self.throughput_rx_bps[dpid][port_no] = (8*(stat.rx_bytes - self.old_rx_bytes[dpid][port_no])) / self.period
            self.throughput_tx_bps[dpid][port_no] = (8*(stat.tx_bytes - self.old_tx_bytes[dpid][port_no])) / self.period

            delta_rx_packets = stat.rx_packets-self.old_rx_packets[dpid][port_no]
            delta_rx_bytes = stat.rx_bytes-self.old_rx_bytes[dpid][port_no]
            delta_tx_packets = stat.tx_packets-self.old_tx_packets[dpid][port_no]
            delta_tx_bytes = stat.tx_bytes-self.old_tx_bytes[dpid][port_no]
    
            self.old_rx_bytes[dpid][port_no] = stat.rx_bytes 
            self.old_tx_bytes[dpid][port_no] = stat.tx_bytes
            self.old_rx_packets[dpid][port_no] = stat.rx_packets
            self.old_tx_packets[dpid][port_no] = stat.tx_packets

            #features derivate utili per rendere il clustering migliore
            bytes_packets_rx_ratio = delta_rx_bytes / (delta_rx_packets + 1e-10)
            bytes_packets_tx_ratio = delta_tx_bytes / (delta_tx_packets + 1e-10)
            efficiency = delta_tx_packets / (delta_rx_packets + delta_tx_packets + 1e-10)
            bandwidth_utilization = (self.throughput_rx_bps[dpid][port_no]+self.throughput_tx_bps[dpid][port_no]) / (self.bandwidth_links[dpid][port_no]*(10**6))
                                                                                
            instance_features = pd.DataFrame([{
                #"dpid" : dpid,
                "dpid" : dpid,
                "port_no" : port_no,
                "delta_rx_packets" : delta_rx_packets,
                "delta_rx_bytes" : delta_rx_bytes,
                "delta_tx_packets" : delta_tx_packets,
                "delta_tx_bytes" : delta_tx_bytes,
                "bytes_packets_rx_ratio" : bytes_packets_rx_ratio,
                "bytes_packets_tx_ratio" : bytes_packets_tx_ratio,
                'efficiency' : efficiency,
                'bandwidth_utilization ' :  bandwidth_utilization,
                "throughput_tx_bps" : self.throughput_tx_bps[dpid][port_no],
                "throughput_rx_bps" : self.throughput_rx_bps[dpid][port_no]
            }])

            #mostriamo solo alcune delle features
            ports.append(("dpid = %d port_no = %d delta_rx_packets = %s delta_rx_bytes = %s delta_tx_packets = %s delta_tx_bytes = %s "
            "throughput_tx_bps = %s throughput_rx_bps= %s") % (dpid,port_no,delta_rx_packets,delta_rx_bytes,delta_tx_packets,delta_tx_bytes,self.throughput_tx_bps[dpid][port_no],
                                                            self.throughput_rx_bps[dpid][port_no]))

            #Prepara la riga del dataset per scriverla nel file
            line = "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                dpid,
                port_no,
                delta_rx_packets,
                delta_rx_bytes,
                delta_tx_packets,
                delta_tx_bytes,
                bytes_packets_rx_ratio,
                bytes_packets_tx_ratio,
                efficiency,
                bandwidth_utilization,
                self.throughput_tx_bps[dpid][port_no],
                self.throughput_rx_bps[dpid][port_no],
            )

            if self.controlAnomaly(np.array(instance_features.drop(instance_features.columns[[0,1]],axis=1))) == True :

                self.logger.info(("\n\n*******Anomaly detected********* (%d,%d)\n\n") % (dpid,port_no))
        
                malicious_ip = [ip for ip, loc in self.host_locations.items() if loc == (dpid, port_no)]

                with self.lock_file :
                    with open(self.log_file,'a') as f :
                        text = "Anomaly detected on flow "+ str(malicious_ip[0]) + " bandwidth_utilization = "
                        text =  text + str(bandwidth_utilization) + " throughput_rx_bps = " + str(self.throughput_rx_bps[dpid][port_no]) + "\n"
                        f.write(text)

                data_queue =  [self.datapaths[dpid],port_no,malicious_ip[0],10]
                try :
                    self.queue.put(data_queue,block=False)
                except  queue.Full :
                  self.logger.info("\n\n****Queue Full proceed with the execution****\n\n")
            
            #scrivi la riga nel file
            #with open(self.name_file, "a") as f: #apro in modalità append
                #f.write(line)

        self.logger.info("****Datapath = %d  Ports = \n",ev.msg.datapath.id)
        for port in ports :
            self.logger.info(port)
        self.logger.info("-------------------------------------------------\n")


    #ricezione packet_in che viene inviato dallo switch al controller quando non sa cosa fare
    @set_ev_cls(ofp_event.EventOFPPacketIn,MAIN_DISPATCHER)
    def packet_in_handler(self,ev) :
        if ev.msg.msg_len < ev.msg.total_len :
            self.logger.debug("Packet truncated only %s bytes received on %s bytes",ev.msg.msg_len,ev.msg_total_len)

        datapath=ev.msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        msg = ev.msg
        in_port = msg.match['in_port']

        pkt = packet.Packet(ev.msg.data) #converto in pacchetto di rete

        eth = pkt.get_protocol(ethernet.ethernet) 

        if eth.ethertype == ether_types.ETH_TYPE_LLDP : #ignoro pacchetti inerenti alla topologia
            return

        #source and destination mach
        eth_src = eth.src
        eth_dst = eth.dst

        self.logger.info("Packet in %s %s %s %s",dpid,eth_src,eth_dst,in_port)

        self.switch_table.setdefault(dpid,{})

        #regola di autoapprendimento switch
        self.switch_table[dpid][eth_src] = in_port

        out_port = None
        if eth_dst in self.switch_table[dpid] :
            out_port = self.switch_table[dpid][eth_dst] 
        else :
            out_port = ofproto.OFPP_FLOOD    #invio su tutte le porte eccetto da quella da cui l'ho ricevuta

        actions = [ofp_parser.OFPActionOutput(out_port)]

        #se non devo fare flood
        if out_port != ofproto.OFPP_FLOOD  :
            match = ofp_parser.OFPMatch(in_port=in_port,eth_src=eth_src,eth_dst=eth_dst)

            if msg.buffer_id != ofproto.OFP_NO_BUFFER : #dato bufferizzato nello switch
                self.add_flow(datapath,match,1,actions,0,msg.buffer_id)
                return #lo switch  ha tutto quello che gli serve per fare il forwarding
            else :
                self.add_flow(datapath,match,1,actions,0)

        data = None
        #se il dato non è bufferizzato invio il dato in packetOut (invio al "volo")
        if msg.buffer_id == ofproto.OFP_NO_BUFFER : 
            data = ev.msg.data

        msg_out = ofp_parser.OFPPacketOut(datapath=datapath,buffer_id=msg.buffer_id,data=data,actions=actions,in_port=in_port)

        datapath.send_msg(msg_out)
