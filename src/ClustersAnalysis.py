# -*- coding: utf-8 -*-
"""
Created on Sat May 24 18:36:10 2025

@author: GIUSEPPE
"""

import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram, linkage
import pandas as pd


def preprocessing(name_file) :
    
    df = pd.read_csv(name_file)

    df = df.drop(df.columns[[0,1]],axis=1)
    
    return df

def KMeansVisualization(df,number_clusters,feature_x,feature_y) :
    
    kmeans = KMeans(n_clusters=number_clusters,random_state=0) 
    
    kmeans.fit(df)
    
    plt.figure()
    plt.scatter(x=df.loc[:,feature_x],y=df.loc[:,feature_y],c=kmeans.labels_)
    plt.title('KMeans Analysis')
    plt.xlabel(feature_x)
    plt.ylabel(feature_y)
    plt.grid()
    return

    
    
'''
Inertia measures how well a 
dataset was clustered by K-Means. 
It is calculated by measuring the distance 
between each data point and its centroid, 
squaring this distance, and summing these squares across one cluster.
'''
def KMeansClusterschoice(df) :
    
    inertia_list = []
    dim_range = 10

    for i in range(1,dim_range) :
        kmeans = KMeans(n_clusters=i,random_state=0)
        kmeans.fit(df)
        inertia_list.append(kmeans.inertia_)
        
    plt.figure()
    plt.plot(np.arange(1,dim_range),inertia_list,label='intertia graph',marker='o')
    plt.title('Cluster choice using KMeans')
    plt.xlabel('number of clusters')
    plt.ylabel('intertia')
    plt.grid()
    
    return
    

def AgglomerativeClusteringChoice(df,method='ward') :
    
    linkage_df = linkage(df,method ='ward',metric = 'euclidean')
    
    plt.figure()
    dendrogram(linkage_df,p=10,truncate_mode='level')
    
    return 


def AgglomerativeClusteringVisualization(df,feature_x,feature_y,linkage='ward') :
    
    hierarchy_cluster = AgglomerativeClustering(n_clusters=3,affinity="euclidean",
                                                linkage=linkage)
    
    hierarchy_cluster.fit(df)
    
    plt.figure()
    plt.scatter(x=df.loc[:,feature_x],y=df.loc[:,feature_y],c=hierarchy_cluster.labels_)
    plt.title('Agglomerative Analysis')
    plt.xlabel(feature_x)
    plt.ylabel(feature_y)
    plt.grid()
    return

    
    
if __name__ == '__main__' :
    
   df = preprocessing('dataset.txt')
   
   AgglomerativeClusteringVisualization(df,'bytes_packets_rx_ratio','bandwidth_utilization','complete')
   
   KMeansClusterschoice(df) 
    
   KMeansVisualization(df,3,'bytes_packets_rx_ratio','bandwidth_utilization')
   
    