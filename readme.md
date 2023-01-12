The scripts in this repo have been written to support exporting of resource
metadata and metrics to allow a team who are migrating from Azure to AWS to
perform pre-migration assessments and plan the capacity and settings of the
target resources being migrated to.

Setup
-----

Install the following Python packages

```
pip3 install -r requirements.txt
```

Authenticate with Azure using your AD credentials

```
az login --use-device-code
```

Update the inventory.json file with relevant subscription IDs, resource group names and resource names. Below is an example of the json format.

```
{
    "b9e10748-d338-4642-a355-853fb8a0da52": {
        "reporting": {
            "Microsoft.DBforMySQL/servers": [
                "my-mysql-single"
            ],
            "Microsoft.DBforMySQL/flexibleServers": [
                "my-mysql-flexi"
            ],
            "Microsoft.Sql/servers": [
                "my-sql/databases/sstero-sql-db1"
            ],
            "Microsoft.Storage/storageAccounts": [
                "mystorageaccount"
            ]
        }
    }
}
```

Execution
---------

The collect_profiles.py script can be used to capture the resource profiles for the following resource types.

- Azure MySQL Single Server
- Azure MySQL Flexible Server
- Azure SQL
- Azure Storage

Note: Using tab separated values format as some metadata descriptions contain commas.

```
./collect_profiles.py -i ./inventory.json -o profiles.tsv
```

The collect_metrics.py script can be used to capture the resource metrics stored
in Azure Monitor. Metrics are captured for the most recent 14 days by default.
Use the '-l' flag to specify a different number of day or the '-s' and '-e'
flags to specify the start/end times explicitely.

```
./collect_metrics.py -i ./inventory.json -m ./metrics.json -o metrics.csv
```

You can modify the metrics.json file with different metric names and aggregation
types. Use the '-d' flag to print the available metric names and aggregation
types for each resource.

```
./collect_metrics.py -i ./inventory.json -m ./metrics.json -d
```