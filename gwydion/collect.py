import logging
import time
from statistics import mean

import matplotlib

from gwydion.gwydion.envs.deployment import get_online_boutique_deployment_list, get_redis_deployment_list
from gwydion.gwydion.envs.util import save_to_csv, get_num_pods

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

logging.basicConfig(filename='collector.log', filemode='w', level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

if __name__ == "__main__":
    reward = 'cost'  # cost, risk or latency
    app = 'onlineboutique'
    min_pods = 1
    max_pods = 8
    k8s = True

    num_episodes = 100
    num_steps = 25
    sleep = 5

    # Deployment Data
    deploymentList = []
    if app == 'onlineboutique':
        deploymentList = get_online_boutique_deployment_list(k8s, min_pods, max_pods)
    elif app == 'redis':
        deploymentList = get_redis_deployment_list(k8s, min_pods, max_pods)

    for i in range(num_episodes):
        avg_pods = []
        avg_latency = []

        for s in range(num_steps):
            for d in deploymentList:
                d.update_obs_k8s()

            avg_pods.append(get_num_pods(deploymentList))
            avg_latency.append(deploymentList[0].latency)

            logging.info('[Step {}] | Pods: {} | Latency: {}'.format(s, avg_pods[s], avg_latency[s]))

            # sleep for a few seconds
            time.sleep(sleep)

        # Save to csv
        save_to_csv('resuts-collect.csv', i, mean(avg_pods), mean(avg_latency), 0, 0)
