import csv
import logging
import numpy as np
import pandas as pd
import requests
from kubernetes import client, config
import time
import os
import math
import statsmodels.tsa.arima.model as arima

# Endpoint of your Kube cluster: kube proxy enabled
# HOST = "http://localhost:8080"

# TOKEN from your cluster
# TOKEN = "hp9b0k.1g9tqz8vkf78ucwf"
from kubernetes.client import ApiException

custom_config = {
    "prometheus_url": os.environ.get("PROMETHEUS_URL", default="http://localhost:9090"),
    "deployment_name": os.environ.get("DEPLOYMENT_NAME", default="teastore-persistence"),
    "deployment_namespace": os.environ.get("DEPLOYMENT_NAMESPACE", default="default"),
    "freq": os.environ.get("FREQ", default=15),  # frequency of annotation. The unit is in seconds
    "forecast": os.environ.get("FORECAST", default=True)  # frequency of annotation. The unit is in seconds
}

logging.basicConfig(filename='estimator.log', filemode='w', level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

class Estimator:
    def __init__(self):
        # Create Kubernetes Client configuration
        self.config = config.load_incluster_config()

        # Create Kubernetes Clients
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

        # token for VWall cluster
        # self.token = TOKEN

        # Create a configuration object
        # self.config = client.Configuration()
        # self.config.verify_ssl = False
        # self.config.api_key = {"authorization": "Bearer " + self.token}

        # Specify the endpoint of your Kube cluster: kube proxy enabled
        # self.config.host = HOST

        # Create a ApiClient with our config
        # self.client = client.ApiClient(self.config)
        # v1 api
        # self.v1 = client.CoreV1Api(self.client)
        # apps v1 api
        # self.apps_v1 = client.AppsV1Api(self.client)

        self.freq = int(custom_config["freq"])
        self.forecast = custom_config["forecast"]
        self.deployment_name = custom_config["deployment_name"]
        self.deployment_namespace = custom_config["deployment_namespace"]
        self.prometheus_url = custom_config["prometheus_url"]
        self.sleep = 5  # 5 seconds for retrying

        self.mem_query = 'sum(rate(container_memory_working_set_bytes{namespace="' + self.deployment_namespace + \
                         '", container=~"' + self.deployment_name + '.*"}[5m])) by (container)'  # by (container) or by (pod)
        self.cpu_query = 'sum(rate(container_cpu_usage_seconds_total{namespace="' + self.deployment_namespace + \
                         '", container=~"' + self.deployment_name + '.*"}[5m])) by (container)'

        # Get deployment object
        self.deployment_object = self.get_deployment()
        # logging.info(self.deployment_object)

        self.mem_file_path = 'mem_usage.csv'
        self.cpu_file_path = 'cpu_usage.csv'

        # Variables for query's
        # self.now = int(time.time())
        # self.start = (self.now - 3600)  # last hour
        # self.end = self.now
        self.step = '60s'  # fetch the data gathered every 15 seconds

        '''
        query_cpu = 'sum(irate(container_cpu_usage_seconds_total{namespace=' \
                    '"' + self.namespace + '", pod="' + p + '"}[5m])) by (pod)'

        query_mem = 'sum(irate(container_memory_working_set_bytes{namespace=' \
                    '"' + self.namespace + '", pod="' + p + '"}[5m])) by (pod)'

        query_received = 'sum(irate(container_network_receive_bytes_total{namespace=' \
                         '"' + self.namespace + '", pod="' + p + '"}[5m])) by (pod)'
        query_transmit = 'sum(irate(container_network_transmit_bytes_total{namespace="' \
                         + self.namespace + '", pod="' + p + '"}[5m])) by (pod)'
        '''

        self.print_deployment()

    def get_deployment(self):
        try:
            return self.apps_v1.read_namespaced_deployment(name=self.deployment_name,
                                                           namespace=self.deployment_namespace)
        except ApiException as e:
            if e.status == 404:
                logging.info("[init] Deployment not found: {}".format(e.reason))
                time.sleep(self.sleep)
                return self.get_deployment()
            else:
                logging.error("[init] API Exception occurred: {}".format(e))
                time.sleep(self.sleep)
                return self.get_deployment()
        except Exception as e:
            logging.info(e)
            logging.info("[init] Exception occurred, retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.get_deployment()

    def fetch_prom(self, query, file, start, end):
        logging.info("[fetch_prom] " + str(query) + " - " + str(file))

        # Update deployment object
        self.deployment_object = self.get_deployment()

        try:
            response = requests.get(self.prometheus_url + '/api/v1/query',
                                    params={'query': query, 'start': start,
                                            'end': end, 'step': self.step})

        except requests.exceptions.RequestException as e:
            logging.info(e)
            logging.info("[fetch_prom] Retrying in {}...".format(self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom(query, file, start, end)

        if response.json()['status'] != "success":
            logging.info("[fetch_prom] Error processing the request: " + response.json()['status'])
            logging.info("[fetch_prom] The Error is: " + response.json()['error'])
            logging.info("[fetch_prom] Retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.fetch_prom(query, file, start, end)

        result = response.json()['data']['result']
        if len(result) == 0:
            logging.info("No data found for the query")
            return

        data = np.array([result[0]['value']])
        # logging.info(data)
        data = pd.DataFrame(data=data, columns=['timestamp', 'value'], dtype=float)

        # Convert datetime string to datetime object
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='s')
        # logging.info(data)

        # Add number of pods as column
        data['num_pods'] = self.deployment_object.spec.replicas

        # Convert data
        # cpu in mCPU
        if file == "cpu_usage.csv":
            data['value'] = data['value'].apply(lambda x: float(x * 1000))
        else:
            # memory in Kib
            data['value'] = data['value'].apply(lambda x: float(x / 1000000))

        # Append the data to a CSV file
        data.to_csv(file, mode='a', header=False, index=False)

        mean = round(data["value"].mean(), 2)
        std = round(data["value"].std(), 2)
        min = round(data["value"].min(), 2)

        if math.isnan(data["value"].std()):
            std = 0.0

        logging.info("[fetch_prom] " +
                     "Avg: " + str(mean) +
                     " - Std: " + str(std) +
                     " - min: " + str(min))

        prediction = self.predict_next(file)
        return result, data, mean, std, min, prediction

    def annotate_deployment(self):
        start = (int(time.time() - 86400))  # last 1h
        end = int(time.time())

        result, cpu_data, cpu_mean, cpu_std, cpu_min, cpu_predicted = self.fetch_prom(query=self.cpu_query,
                                                                                      file=self.cpu_file_path,
                                                                                      start=start,
                                                                                      end=end)
        if cpu_predicted == 0:
            cpu_predicted = "N/A"
        else:
            cpu_predicted = "{:.3f}".format(cpu_predicted)

        result, mem_data, mem_mean, mem_std, mem_min, mem_predicted = self.fetch_prom(query=self.mem_query,
                                                                                      file=self.mem_file_path,
                                                                                      start=start,
                                                                                      end=end)
        if mem_predicted == 0:
            mem_predicted = "N/A"
        else:
            mem_predicted = "{:.3f}".format(mem_predicted)

        logging.info("[annotate] CPU - Avg: " + str(cpu_mean) + " - Std: " + str(cpu_std) + " - min: " + str(cpu_min))
        logging.info("[annotate] MEM - Avg: " + str(mem_mean) + " - Std: " + str(mem_std) + " - min: " + str(mem_min))

        body = {
            "metadata": {
                "annotations": {
                    "mean-memory-usage": str("{:.3f}".format(mem_mean)) + "Mi",
                    "mean-cpu-usage": str("{:.3f}".format(cpu_mean)) + "m",
                    "std-memory-usage": str("{:.3f}".format(mem_std)) + "Mi",
                    "std-cpu-usage": str("{:.3f}".format(cpu_std)) + "m",
                    "forecast-arima-memory-usage": str(mem_predicted) + "Mi",
                    "forecast-arima-cpu-usage": str(cpu_predicted) + "m",

                }
            }
        }

        logging.info(body)

        self.patch_deployment(body=body)

    def main(self):
        self.annotate_deployment()
        logging.info("[main] Sleeping for " + str(self.freq) + " seconds ...")
        time.sleep(self.freq)

    def patch_deployment(self, body):
        try:
            self.apps_v1.patch_namespaced_deployment(
                name=self.deployment_name, namespace=self.deployment_namespace, body=body
            )
        except Exception as e:
            logging.info(e)
            logging.info("[patch] Retrying in {}s...".format(self.sleep))
            time.sleep(self.sleep)
            return self.patch_deployment(body)

    def print_deployment(self):
        logging.info("Name: " + str(self.deployment_name))
        logging.info("Namespace: " + str(self.deployment_namespace))
        logging.info("Number of pods: " + str(self.deployment_object.spec.replicas))
        # logging.info("[Deployment] Desired Replicas: " + str(self.desired_replicas))
        # logging.info("[Deployment] Pod Names: " + str(self.pod_names))
        # logging.info("[Deployment] MAX Pods: " + str(self.max_pods))
        # logging.info("[Deployment] MIN Pods: " + str(self.min_pods))
        # logging.info("[Deployment] CPU Usage (in m): " + str(self.cpu_usage))
        # logging.info("[Deployment] MEM Usage (in Mi): " + str(self.mem_usage))
        # logging.info("[Deployment] Received traffic (in Kbit/s): " + str(self.received_traffic))
        # logging.info("[Deployment] Transmit traffic (in Kbit/s): " + str(self.transmit_traffic))

        # if self.lstm_enabled:
        #    logging.info("[Deployment] LSTM 1-step CPU Prediction: " + str(
        #        self.lstm_cpu_step_1))  # missing: deploy CPU predictor pod
        #    logging.info("[Deployment] LSTM 5-step CPU Prediction: " + str(
        #        self.lstm_cpu_step_5))  # missing: deploy CPU predictor pod

    @staticmethod
    def predict_next(file, chunk_divider=10, steps=1):
        try:
            # Read the CSV file
            df = pd.read_csv(file)
            data = df['value'].values

            # Replace zero values with the median
            non_zero_data = data[data != 0]
            median_value = np.median(non_zero_data)
            data[data == 0] = median_value

            # Return prediction if less than 10 samples
            if len(data) < 10:
                # Return prediction
                logging.info("[ARIMA] Return 0.0 as prediction, less than 10 samples...")
                return 0.0

            # Overwrite chunk divider
            elif len(data) > 1000:
                chunk_divider = 100

            # Split the data into chunks
            chunk_size = len(data) // chunk_divider
            chunks = np.array_split(data, chunk_divider)

            # Calculate the means of the chunks
            means = [np.mean(chunk) for chunk in chunks]

            # Fit an ARIMA model
            model = arima.ARIMA(means, order=(5, 1, 0))
            model_fit = model.fit()

            # Make a one-step forecast
            predicted = model_fit.forecast(steps=steps)[0]
            logging.info("[ARIMA] Prediction: " + str(predicted))

            # Return prediction
            return predicted

        except Exception as e:
            logging.info("[ARIMA] Error occurred while predicting: " + str(e))
            return 0.0


if __name__ == '__main__':
    est = Estimator()
    logging.info("Deployment annotator starting ...")
    while True:
        est.main()
