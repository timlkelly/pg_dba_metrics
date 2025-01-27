#!/usr/bin/env python
# -*- coding: utf-8 -*-
# TODO: Add status & threshold to output and table
import argparse
import json
import os
import yaml
from pathlib import Path

import records
from apscheduler.schedulers.blocking import BlockingScheduler
from dba_metrics.alert import check_metric
from dotenv import find_dotenv, load_dotenv
from nerium.formatter import get_format
from nerium.query import get_result_set

override = False
if os.getenv("METRIC_ENV", "development") == "development":
    override = True

load_dotenv(find_dotenv(), override=override)

HOSTNAME = os.getenv("HOSTNAME", "localhost")
INTERVAL = int(os.getenv("INTERVAL", 60))
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres@localhost/yardstick")
STORE_DB_URL = os.getenv("STORE_DB_URL", DATABASE_URL)

store_db = records.Database(
    STORE_DB_URL, connect_args={"application_name": "pg_dba_metrics"}
)


def get_metric(name, quiet=False):
    metric = get_result_set(name)
    metric.executed += "Z"
    metric = check_metric(metric)
    return metric


def print_metric(name):
    metric = get_metric(name)
    format = get_format("print")
    formatted = yaml.safe_dump(format.dump(metric).data)
    return formatted


def store_metric(name):
    metric = get_metric(name)
    # fmt: off
    sql = (
        "INSERT into perf_metric ("
        "   stamp, "
        "   payload, "
        "   name, "
        "   host, "
        "   status, "
        "   threshold_field, "
        "   threshold_gate) "
        "VALUES ("
        "   :stamp, "
        "   :payload, "
        "   :name, "
        "   :host, "
        "   :status, "
        "   :threshold_field, "
        "   :threshold_gate) "
        "returning metric_id"
    )
    # fmt: on
    for i in metric.result:
        stamp = metric.executed
        payload = json.dumps(i, default=str)
        status = metric.status
        threshold_field = metric.threshold["field"]
        threshold_gate = str(metric.threshold["gate"])
        print(stamp, payload, status, threshold_field, threshold_gate)
        insert = store_db.query(
            sql,
            stamp=stamp,
            payload=payload,
            name=name,
            host=HOSTNAME,
            status=status,
            threshold_field=threshold_field,
            threshold_gate=threshold_gate,
        )
        return insert.export("json")


def all_metrics():
    metrics = list(Path(os.getenv("QUERY_PATH", "query_files")).glob("**/*"))
    metric_names = [metric.stem for metric in metrics]
    return metric_names


def output_all(output_function, name="all"):
    if name == "all":
        metrics = all_metrics()
    else:
        metrics = [name]
    for name in metrics:
        output = output_function(name)
        print(output)
        # yield output


def schedule(output_function, name="all"):
    """Schedule get_metrics job in APScheduler, set to run at configured $INTERVAL
    """
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(output_all, "interval", [output_function, name], seconds=INTERVAL)
    print("Press Ctrl+C to exit")

    # Execution will block here until Ctrl+C is pressed.
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


def create_table():
    """Create table for storing metrics in target database if not present
    """
    sql = (
        "create table if not exists perf_metric( "
        "metric_id bigserial primary key, "
        "stamp timestamp with time zone, "
        "payload jsonb, "
        "name text, "
        "host text, "
        "status text, "
        "threshold_field text, "
        "threshold_gate int)"
    )
    store_db.query(sql)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="all")
    parser.add_argument("-s", "--store", action="store_true", default=False)
    parser.add_argument("-S", "--schedule", action="store_true", default=False)
    args = parser.parse_args()

    output_function = print_metric
    if args.store:
        create_table()
        output_function = store_metric

    if args.schedule:
        schedule(output_function, args.name)
    else:
        output_all(output_function, args.name)


if __name__ == "__main__":
    main()
