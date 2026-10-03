import time
import threading
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

#Progetto un controller che monitora il traffico sulla porta di output del secondo switch

class SwitchController(app_manager.RyuApp) :

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self,*args,**kwargs) :
        super(SwitchController,self).__init__(*args,**kwargs)
        self.switch_table = {} #dizionario in cui per ogni switch è memorizzato un dizionario
        #coppia (MAC,in_port)
        self.hosts_info = 'hosts_info.txt'
        self.host_locations = {} #uso come chiave il MAC del'host e come valore la tupla che specifica
        #la coppia dpid,port_no (a cui l'host è connesso)
        self.bandwidth_links = {}
        self.infoHosts()
        self.datapaths = {} #un dizionario che contiene per ogni switchOpenFlow il relativo datapath
        #(come chiave usiamo il datapath.id)
        self.period = 5  #periodo di 5 secondi
        self.old_rx_bytes = {} #i primi due dizionario contengono per coppia (id_switch,port) il numero
        #di byte ricevuti 
        self.old_tx_bytes = {}
        self.throughput_tx_bps = {} #i restanti due il throughput sia in ricezione che trasmissione
        self.throughput_rx_bps = {}
        self.threshold = 3 *(10**6) #soglia espressa in bps
        self.monitor_thread = threading.Thread(target = self.request_port_status)
        self.monitor_thread.daemon=True
        self.monitor_thread.start()

    #decoratore : gestiamo l'evento in cui ad esempio uno switch si disconnette e cosi via
    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER,DEAD_DISPATCHER])
    def state_change_handler(self,ev) :
        datapath = ev.datapath  #l'evento in questo casa avrà almeno come attributo datapath

        if ev.state == MAIN_DISPATCHER :
            if datapath.id not in self.datapaths.keys() : #se lo switch non è presente (potevo usare anche is no)
                self.datapaths[datapath.id] = datapath #lo inserisco
        elif ev.state == DEAD_DISPATCHER : #ad esempio lo switch si è disconnesso
            if datapath.id in self.datapaths.keys() : #potevo usare anche is invece che in
                del self.datapaths[datapath.id] #elimino la chiave con il relativo valore


    def infoHosts(self) :
        with open(self.hosts_info,'r') as f:
            next(f)
            for line in f :
                fields = line.strip().split(',')
                self.bandwidth_links.setdefault(int(fields[0]),{})
                self.bandwidth_links[int(fields[0])][int(fields[1])] = float(fields[3])
                self.host_locations[str(fields[2])] = (int(fields[0]),int(fields[1]))

    '''Funzione per bloccare un porta aggiungendo una regola con un timeout'''
    def block_port(self,datapath,port_no,hard_timeout) :
        ofp_parser = datapath.ofproto_parser
    
        actions =[]

        match = ofp_parser.OFPMatch(in_port = port_no)

        self.add_flow(datapath,2,match,actions,hard_timeout) #metto una priorità piu alta
        #con hard_timeout secondi dopo il quale la regola è rimossa (verrà matchata un altra regola con priorità
        #immediatamente inferiore)

    #MAIN_DISPATCHER: Gestisce eventi da dispositivi di rete attivi e funzionanti.
    #Gestisce la comunicazione normale tra il controller e gli switch.
    #decoratore gestiamo l'evento in cui il controller riceve le statistiche sullo stato delle porte
    #il dispatcher indica la fase di negoziazione in cui l'evento deve essere generato
    @set_ev_cls(ofp_event.EventOFPPortStatsReply,MAIN_DISPATCHER)
    def port_stats_handler(self,ev) :

        #inizializzo i dizionari con chiave pari all'id del datapath a {} cioè dizionario annidato vuoto
        self.throughput_rx_bps.setdefault(ev.msg.datapath.id,{})
        self.throughput_tx_bps.setdefault(ev.msg.datapath.id,{})
        self.old_rx_bytes.setdefault(ev.msg.datapath.id,{})
        self.old_tx_bytes.setdefault(ev.msg.datapath.id,{})

        
        body = ev.msg.body #body è una lista di OFPPortStats
        #le statistiche di RYU sono cumulative : 
        #Statistiche cumulative significa che ogni nuova misurazione aggiunge al 
        #totale accumulato precedentemente
        #Questo ti dà il totale complessivo di pacchetti (o byte, o qualsiasi altra metrica) 
        #che sono passati attraverso quella porta da quando è stata inizializzata.

        ports = []
        for stat in body :

            if stat.port_no  == ofproto_v1_3.OFPP_LOCAL : 
                continue
            
            dpid = ev.msg.datapath.id      
            port_no = stat.port_no

            self.old_rx_bytes[dpid].setdefault(port_no,0)
            self.old_tx_bytes[dpid].setdefault(port_no,0)

            #per ottenere bit per secondo moltiplico per 8 dato che 1 byte sono 8 bits   
            self.throughput_rx_bps[dpid][port_no]= (8*(stat.rx_bytes - self.old_rx_bytes[dpid][port_no])) / self.period
            self.throughput_tx_bps[dpid][port_no]= (8*(stat.tx_bytes - self.old_tx_bytes[dpid][port_no])) / self.period
            
            #aggiornamento valore dei byte ricevuti in ricezione e trasmissione
            self.old_rx_bytes[dpid][port_no] = stat.rx_bytes
            self.old_tx_bytes[dpid][port_no] = stat.tx_bytes

            ports.append("dpid = %d port_no = %d thrughput_rx_bps = %d thrughput_tx_bps = %d"
                        % (
                        dpid,stat.port_no,self.throughput_rx_bps[dpid][stat.port_no],self.throughput_tx_bps[dpid][stat.port_no]
                        ))
            
            if self.throughput_rx_bps[dpid][port_no] > self.threshold :
                self.logger.info("\n\n\n*******Superamento soglia dpid = %d port_no = %d ******\n\n\n",dpid,port_no)
                self.logger.info("\n\n******Blocking port*****\n\n")
                self.block_port(self.datapaths[dpid],port_no = port_no,hard_timeout=10) #aggiungo una regola
                #hard_timeout indica il massimo tempo in secondi prima che venga rimossa la regola dalla flow-table
      
      
        for port in ports :
            self.logger.info(port)
        self.logger.info("------------------------------------------------")


    #questa funzione richiede lo stato di una porta di uno switch
    #usando il metodo OFPPortStatsRequest
    #se voglio chiedere una info su tutte le porte basta porre OFPP_ANY
    #richiesta dello stato delle porte degli switch specificati nel file hosts_info.txt
    def request_port_status(self) :
        while True :

            msg_list = []

            for dpid,port in self.host_locations.values() :

                if dpid in self.datapaths.keys() :
                    ofp_parser = self.datapaths[dpid].ofproto_parser

                    #lista di tuple (dpid (per poi da self.datapaths prenderne il datapath),messaggio da mandare)
                    msg_list.append((dpid,ofp_parser.OFPPortStatsRequest(datapath=self.datapaths[dpid],flags=0,port_no = port)))
    

            for dpid,msg_out in msg_list :
                self.datapaths[dpid].send_msg(msg_out)

            time.sleep(self.period)


    #decoratore per gestire l'evento in cui lo switch invia le sue features al controller
    #useremo il CONFIG_DISPATCHER
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures,CONFIG_DISPATCHER) 
    def switch_features_handler(self,ev) :

        msg = ev.msg
        datapath = msg.datapath #consente di identificare lo switch
        ofproto = datapath.ofproto #per usare alcune costanti di OpenFlow
        ofp_parser = datapath.ofproto_parser #per permette al controller e allo switch di interagire

        match = ofp_parser.OFPMatch() #match con qualunque pacchetto
        #installeremo una regola di defualt

        #l'azione è mandare il messaggio al controller, senza limite alla max length da mandargli
        actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,ofproto.OFPCML_NO_BUFFER)]

        self.add_flow(datapath,0,match,actions,0)



    def add_flow(self,datapath,priority,match,actions,hard_timeout,buffer_id=None) :

        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        instr = [ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,actions)]

        msg_out = None
        if buffer_id :
            msg_out = ofp_parser.OFPFlowMod(datapath=datapath,priority=priority,match=match,buffer_id=buffer_id,
                                        instructions=instr,hard_timeout = hard_timeout)
        else:
            msg_out = ofp_parser.OFPFlowMod(datapath=datapath,priority=priority,match=match,
                                        instructions=instr,hard_timeout = hard_timeout)    
    
        datapath.send_msg(msg_out)




    #decoratore handler invocato quanto il controller riceve un PacketIn dallo switch, il quale non ha trovato alcuna 
    #corrispondenza nella flow table
    @set_ev_cls(ofp_event.EventOFPPacketIn,MAIN_DISPATCHER)
    def packet_in_handler(self,ev) :

        #segnalo se il pacchetto è frammentato
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        id_switch = datapath.id
        data = msg.data

        pkt = packet.Packet(data) #converto in pacchetto di rete (con i vari protocolli e stack)
        
        eth = pkt.get_protocol(ethernet.ethernet) #primo tipo di protocollo che matcha con il protocollo passato in ingresso
       
        if eth.ethertype == ether_types.ETH_TYPE_LLDP : #ignoro pacchetti LLDP che riguardano la topologia
            return

        src = eth.src
        dst = eth.dst 
        #eth ha tre campi : src, dst, ethertype (che ci informa del tipo di protocollo del livello superiore)

        #uso come livello di debg info che da informazioni di debug generali
        self.logger.info('Packet in %s %s %s %s ',id_switch,src,dst,in_port)

        self.switch_table.setdefault(id_switch,{}) #assegno un valore di default
        #che ha effetto se la chiave non esiste però
        
        #memorizzo il porto da cui ho ricevuto il primo pacchetto con quel MAC_ADDRESS sorgente
        self.switch_table[id_switch][src] = in_port

        outport = None
        if dst in self.switch_table[id_switch] :
            outport = self.switch_table[id_switch][dst]
        else :
            outport = ofproto.OFPP_FLOOD #faccio flooding se non trovo una corrispondenza nella switch-table

        #l'azione è inoltre o in flooding o su outport
        actions = [ofp_parser.OFPActionOutput(outport)]
        #SE NON DEVO FARE FLOODING, PARTO DAL DEFINIRE UN MATCH
        if outport != ofproto.OFPP_FLOOD :
            match = ofp_parser.OFPMatch(eth_src = src,eth_dst = dst,in_port = in_port)

            if msg.buffer_id != ofproto.OFP_NO_BUFFER :#se il messaggio è bufferizzato
            #aggiungo la regola nella flow-table ed esco poichè lo switch ha tutti gli strumenti per effettuare il forwarding
                self.add_flow(datapath,1,match,actions,0,msg.buffer_id)
                return
            else : #la regola l'aggiungo la stesso, non specifio l'id del buffer e dovrò procedere con un PacketOut
                self.add_flow(datapath,1,match,actions,0)
            
        msg_out = None
        #se il pacchetto non è bufferizzato includo data in PacketOut
        #æltrimenti metto data a None e specifico l'id del buffer dello switch
        #PacketOut consente di specificare le azioni da fare con quel pacchetto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER :
            
            msg_out = ofp_parser.OFPPacketOut(datapath=datapath,buffer_id = ofproto.OFP_NO_BUFFER,data=data,
                                              actions=actions,in_port = in_port)

        else :

            msg_out = ofp_parser.OFPPacketOut(datapath=datapath,buffer_id = msg.buffer_id,data=None,
                                              actions=actions,in_port = in_port)

        datapath.send_msg(msg_out)

