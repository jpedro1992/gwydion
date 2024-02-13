# Gwydion

The implemented Gwydion is a custom [OpenAi Gym](https://gym.openai.com/) 
environment for the training of Reinforcement Learning (RL) agents for auto-scaling research 
in the Kubernetes (K8s) platform. 


## How does it work?

Two environments exist based on the [Redis Cluster](https://github.com/bitnami/charts/tree/master/bitnami/redis-cluster) and [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) applications. 

Both RL environments have been designed: actions, observations, reward function. 

Please check the [run.py](policies/run/run.py) file to understand how to run the framework. 

To run in the real cluster mode, you should add the token to your cluster [here](gym_hpa/envs/deployment.py)


