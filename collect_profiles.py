#!/usr/bin/env python3

import argparse
import json
import sys
from azure.identity import AzureCliCredential
import azure.mgmt.rdbms.mysql
import azure.mgmt.rdbms.mysql_flexibleservers
import azure.mgmt.sql
import azure.mgmt.storage

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inventory-file", help="Filepath of json file listing inventory of resources to collect profiles for")
    parser.add_argument("-o", "--output-file", help="Filepath to write profiles to in tsv format")
    return parser.parse_args()

def flatten_data(d, prefix=[]):
    output = {}
    def flatten(x, name=[]):
        for k, v in x.items():
            if type(v) in [str, int]:
                output['.'.join(prefix + name + [k])] = v
            elif type(v) is dict:
                flatten(v, name=name + [k])
    flatten(d)
    return output

def write_key_values(output_file, prefix_fields, data, data_type):
    for name, value in sorted(data.items()):
        fields = prefix_fields + [data_type, name, str(value)]
        string = '\t'.join(fields)
        output_file.write(f'{string}\n')

def write_mysql_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name):
    prefix_fields = [subscription_id, resource_group_name, provider, resource_name]
    server = client.servers.get(resource_group_name, resource_name)
    server_info = flatten_data(server.serialize())
    write_key_values(output_file, prefix_fields, server_info, 'property')
    configs = client.configurations.list_by_server(resource_group_name, resource_name)
    for config in sorted(configs, key=lambda x: x.name):
        parameter_fields = prefix_fields + ['parameter', config.name, str(config.value), config.description]
        parameter_string = '\t'.join(parameter_fields)
        output_file.write(f'{parameter_string}\n')

def write_sql_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name):
    prefix_fields = [subscription_id, resource_group_name, provider, resource_name]
    resource_fields = resource_name.split('/')
    server_name = resource_fields[0]
    database_name = resource_fields[-1]
    database = client.databases.get(resource_group_name, server_name, database_name)
    database_info = flatten_data(database.as_dict())
    write_key_values(output_file, prefix_fields, database_info, 'property')
    
def write_storage_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name):
    prefix_fields = [subscription_id, resource_group_name, provider, resource_name]
    account_properties = flatten_data(client.storage_accounts.get_properties(resource_group_name, resource_name).as_dict(), prefix=['account'])
    write_key_values(output_file, prefix_fields, account_properties, 'property')
    for container in client.blob_containers.list(resource_group_name, resource_name):
        container_properties = flatten_data(container.as_dict(), prefix=['container', container.name])
        write_key_values(output_file, prefix_fields, container_properties, 'property')
    for fileshare in client.file_shares.list(resource_group_name, resource_name):
        fileshare_properties = flatten_data(fileshare.as_dict(), prefix=['fileshare', fileshare.name])
        write_key_values(output_file, prefix_fields, fileshare_properties, 'property')

def write_profiles(output_file, credentials, inventory):
    header_fields = ['subscription', 'resource_group_name', 'provider', 'resource_name', 'type', 'name', 'value', 'description']
    header_string = '\t'.join(header_fields)
    output_file.write(f'{header_string}\n')
    clients = {
        'Microsoft.DBforMySQL/servers': {
            'class': azure.mgmt.rdbms.mysql.MySQLManagementClient,
            'client': {},
        },
        'Microsoft.DBforMySQL/flexibleServers': {
            'class': azure.mgmt.rdbms.mysql_flexibleservers.MySQLManagementClient,
            'client': {},
        },
        'Microsoft.Sql/servers': {
            'class': azure.mgmt.sql.SqlManagementClient,
            'client': {},
        },
        'Microsoft.Storage/storageAccounts': {
            'class': azure.mgmt.storage.StorageManagementClient,
            'client': {},
        },
    }
    for subscription_id, subscription_data in inventory.items():
        for resource_group_name, resource_group_data in subscription_data.items():
            for provider, resource_names in resource_group_data.items():
                if subscription_id not in clients[provider]['client']:
                    clients[provider]['client'][subscription_id] = clients[provider]['class'](credentials, subscription_id)
                client = clients[provider]['client'][subscription_id]
                for resource_name in resource_names:
                    if provider in ['Microsoft.DBforMySQL/servers', 'Microsoft.DBforMySQL/flexibleServers']:
                        write_mysql_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name)
                    elif provider == 'Microsoft.Sql/servers':
                        write_sql_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name)
                    elif provider == 'Microsoft.Storage/storageAccounts':
                        write_storage_profile(output_file, client, subscription_id, resource_group_name, provider, resource_name)


if __name__ == '__main__':
    args = parse_args()
    credentials = AzureCliCredential()
    inventory = json.load(open(args.inventory_file))
    output_file = None
    if args.output_file:
        output_file = open(args.output_file, 'w')
    else:
        output_file = sys.stdout
    write_profiles(output_file, credentials, inventory)
    output_file.close()