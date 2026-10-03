import threading
import time
import random
from  mininet.net import Mininet,CLI
from mininet.node import OVSKernelSwitch,Host
from mininet.node import DefaultController,RemoteController
from mininet.link import TCLink,Link
from mininet.log import setLogLevel, info

class Environmnet(object) :

    def __init__ (self) :

        #Create a network
        #self.network = Mininet(controller=DefaultController,link = TCLink) #uso il controller di default
        #network è un oggetto di tipo mininet.net.Mininet
        self.network = Mininet(controller=RemoteController,link = TCLink) 
        info('***Starting controller\n')

        #self.c1 = self.network.addController(str='c1',controller=DefaultController)
        c1 = self.network.addController(str='c1',controller=RemoteController)

        c1.start() #start controller

        info('**Adding hosts and switches**\n')

        #10.0.0.0 - 10.255.255.255 (Classe A) gruppo di indirizzi IP locali 
        #h0,h1,h3 saranno variabili membro della classe
        self.h1 = self.network.addHost(name='h1',mac='00:00:00:00:00:01',ip='10.0.0.1')
        self.h2 = self.network.addHost(name='h2',mac='00:00:00:00:00:02',ip='10.0.0.2')
        self.h3 = self.network.addHost(name='h3',mac='00:00:00:00:00:03',ip='10.0.0.3')

        self.s1 = self.network.addSwitch(name='s1',cls = OVSKernelSwitch)
        self.s2 = self.network.addSwitch(name='s2',cls = OVSKernelSwitch)
        self.s3 = self.network.addSwitch(name='s3',cls = OVSKernelSwitch)
        self.s4 = self.network.addSwitch(name='s4',cls = OVSKernelSwitch)

        info('***Adding Links****\n')

        #bw = banda di trasmissione pari a 2Mbs
        self.h1_s1 = self.network.addLink(node1=self.h1,node2=self.s1,cls=TCLink,bw=6,delay='5ms')
        self.h2_s2 = self.network.addLink(node1=self.h2,node2=self.s2,cls=TCLink,bw=6,delay='5ms')
        self.s1_s3 = self.network.addLink(node1=self.s1,node2=self.s3,cls=TCLink,bw=5,delay='20ms')
        self.s2_s3 = self.network.addLink(node1=self.s2,node2=self.s3,cls=TCLink,bw=5,delay='20ms')
        self.s3_s4 = self.network.addLink(node1=self.s3,node2=self.s4,cls=TCLink,bw=5,delay='20ms')
        self.s4_h3 =self.network.addLink(node1=self.s4,node2=self.h3,cls=TCLink,bw=8,delay='5ms')
    
        info('***Starting network***\n')

        self.network.build() #costruisco la rete (build the network)
        self.network.start() #starta la rete (start the network)


if __name__ == '__main__' :

    setLogLevel('info') #set level log ('INFO': This is the default log level, 
    #showing general information about the Mininet operations )

    info('starting the environment\n')

    ev = Environmnet()

    info('***Running CLI\n')
    CLI(ev.network)


