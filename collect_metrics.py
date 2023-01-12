#!/usr/bin/env python3

from collections import defaultdict
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from azure.identity import AzureCliCredential
from azure.monitor.query import MetricsQueryClient

from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
disable_warnings(InsecureRequestWarning)

default_n_days = 14

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--inventory-file', help='Filepath of json file listing inventory of resources to collect metrics for')
    parser.add_argument('-m', '--metrics-query-file', help='Filepath of json file listing metrics to query')
    parser.add_argument('-o', '--output-file', help='Filepath to write metrics to in csv format')
    parser.add_argument('-d', '--definitions-only', action='store_true', help='Print metric definitons only')
    parser.add_argument('-s', '--start-time', help='The start time to query from. Example: 2023-01-01T00:00:00+08:00')
    parser.add_argument('-e', '--end-time', help='The end time to query to. Defaults to now. Example: 2023-02-01T00:00:00+08:00')
    parser.add_argument('-l', '--last-n-days', help=f'The number of days to start query from until now. Default: {default_n_days}')
    return parser.parse_args()


def print_metric_names(metrics_client, subscription_id, resource_group_name, provider, resource_name):
    resource_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/{provider}/{resource_name}'
    print(f'Resource: {resource_id}')
    print('Metrics')
    for m in metrics_client.list_metric_definitions(resource_id):
        available_aggregation_types = ",".join([t.lower() for t in m.supported_aggregation_types])
        print(f'- {m.name} aggregations:{available_aggregation_types} unit:{m.unit}')
    print('Example Configs')
    for m in metrics_client.list_metric_definitions(resource_id):
        print(f'{{ "metric_name": "{m.name}", "aggregation": "{m.primary_aggregation_type.lower()}" }},')

def get_metrics(query_settings, metrics_client, subscription_id, resource_group_name, provider, resource_name, aggregation, metric_names):
    resource_id = f'/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/{provider}/{resource_name}'
    result = metrics_client.query_resource(resource_id,
        metric_names=metric_names,
        timespan=query_settings.timespan,
        granularity=query_settings.granularity,
        aggregation=aggregation,
        )
    for metric in result.metrics:
        if len(metric.timeseries) == 0:
            continue
        unit = metric.unit
        metric_timeseries = metric.timeseries[0].data
        for metric_data in metric_timeseries:
            if getattr(metric_data, aggregation):
                timestamp = metric_data.timestamp.isoformat()
                metric_value = getattr(metric_data, aggregation)
                yield f'{subscription_id},{resource_group_name},{provider},{resource_name},{metric.name},{unit},{aggregation},{timestamp},{metric_value}\n'

def write_metrics(output_file, query_settings, inventory):
    credential = AzureCliCredential()
    metrics_client = MetricsQueryClient(credential)
    output_file.write(f'subscription,resource_group_name,provider,resource_name,metric_name,unit,aggregation,timestamp,metric_value\n')
    for subscription_id, subscription_data in inventory.items():
        for resource_group_name, resource_group_data in subscription_data.items():
            for provider, resource_names in resource_group_data.items():
                for resource_name in resource_names:
                    if query_settings.print_definitions_only:
                        print_metric_names(metrics_client, subscription_id, resource_group_name, provider, resource_name)
                    else:
                        metric_results = []
                        for aggregation, metric_names in query_settings.metrics_by_aggregation[provider].items():
                            limit = 20
                            for index in range(0, len(metric_names), limit):
                                metric_name_subset = metric_names[index:index+limit]
                                metric_results.extend(get_metrics(
                                    query_settings,
                                    metrics_client,
                                    subscription_id,
                                    resource_group_name,
                                    provider,
                                    resource_name,
                                    aggregation,
                                    metric_name_subset
                                    ))
                        output_file.write(''.join(sorted(metric_results)))


class QuerySettings:
    def __init__(self, args, metrics_query_settings):
        self.load_timespan(args)
        self.load_granularity(metrics_query_settings)
        self.load_metrics(metrics_query_settings)
        self.print_definitions_only = args.definitions_only

    def load_timespan(self, args):
        if args.last_n_days:
            self.start_time = datetime.now(timezone.utc) - timedelta(days=args.last_n_days)
        elif args.start_time:
            self.start_time = datetime.fromisoformat(args.start_time)
        else:
            self.start_time = datetime.now(timezone.utc) - timedelta(days=default_n_days)

        if args.end_time:
            self.end_time = datetime.fromisoformat(args.end_time)
        else:
            self.end_time = datetime.now(timezone.utc)
        
        self.timespan = (self.start_time, self.end_time)
        self.timespan_isoformat = (self.start_time.isoformat(), self.end_time.isoformat())

    def load_granularity(self, metrics_query_settings):
        params = {metrics_query_settings['granularity']['type']: metrics_query_settings['granularity']['count']}
        self.granularity = timedelta(**params)

    def load_metrics(self, metrics_query_settings):
        self.metrics_by_aggregation = defaultdict(lambda: defaultdict(list))
        for provider, metrics_to_query in metrics_query_settings['queries'].items():
            for metric in metrics_to_query:
                for aggregation in metric["aggregations"]:
                    self.metrics_by_aggregation[provider][aggregation].append(metric['metric_name'])

if __name__ == '__main__':
    args = parse_args()
    inventory = json.load(open(args.inventory_file))
    metrics_query_settings = json.load(open(args.metrics_query_file))
    query_settings = QuerySettings(args, metrics_query_settings)
    print(f'using timespan: {query_settings.timespan_isoformat}')
    output_file = None
    if args.output_file:
        output_file = open(args.output_file, 'w')
    else:
        output_file = sys.stdout
    write_metrics(output_file, query_settings, inventory)
    output_file.close()