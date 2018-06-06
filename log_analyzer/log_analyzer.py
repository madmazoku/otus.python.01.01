#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# log_format ui_short '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER"'
#                     '$request_time';

import argparse
import json
import logging
import os
import pathlib
import re
import tempfile
import subprocess
import time
import shutil
import random
import csv
import gzip
import collections
import datetime
from string import Template
import functools

DEFAULT_CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "REPORT_TEMPLATE": "./report.html",
    "LOG_DIR": "./log",
    "PARSE_ERROR_RATE": 0.01,
    "SCRIPT_LOG_PATH": None
}
DEFAULT_CONFIG_JSON_PATH = './config.json'

# LOG_PARSE_PATTERN = re.compile('.+"(?:GET|HEAD|POST|PUT|DELETE|CONNECT|OPTIONS|TRACE|PATCH)\\s([^\\s]+)\\s.+\\s([\\d\\.]+)\\n')
LOG_NAME_PATTERN = re.compile('nginx-access-ui.log-(\\d{8})(\\.gz)?')
LOG_PARSE_PATTERN = re.compile('.+?\\]\\s"[^\\s"]+\\s([^\\s"]+)\\s.+\\s([\\d\\.]+)\\n')

LogInfo = collections.namedtuple('LogInfo', 'file_path date is_gz')
LogRecord = collections.namedtuple('LogRecord', 'url process_time')
UrlsInfo = collections.namedtuple('UrlsInfo', 'info count time_sum')


class Config:
    def __init__(self, config_json_name):
        if config_json_name is None:
            self.config_json_path = pathlib.Path(DEFAULT_CONFIG_JSON_PATH)
        else:
            self.config_json_path = pathlib.Path(config_json_name)

        config_json = None
        with open(str(self.config_json_path)) as config_json_file:
            config_json = json.load(config_json_file)

        config = {}
        config.update(DEFAULT_CONFIG)
        config.update(config_json)

        self.config = config

    def __getattr__(self, key):
        if key in self.config:
            return self.config[key]
        else:
            raise AttributeError


def prepare_environment():
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument("--config", help="path to configuration file in json format", type=str)
    args = args_parser.parse_args()

    config = Config(args.config)

    logging.basicConfig(
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S',
        level='INFO',
        filename=config.SCRIPT_LOG_PATH)

    report_dir_path = pathlib.Path(config.REPORT_DIR)
    if not report_dir_path.is_dir():
        report_dir_path.mkdir(parents=True, exist_ok=True)

    return config


def dump_config(config):
    logging.info("Scrip started")
    logging.info("CONFIG: %s", config.config_json_path)
    for k in sorted(config.config):
        v = config.config[k]
        logging.info('\t%s: %s', k, v)


def find_last_log(config):
    log_info = None

    log_dir_path = pathlib.Path(config.LOG_DIR)
    if log_dir_path.is_dir():

        last_file_path = None
        last_date = None
        last_is_gz = None

        for file_path in log_dir_path.iterdir():
            if not file_path.is_file():
                continue

            match = re.fullmatch(LOG_NAME_PATTERN, file_path.name)
            if match is not None:
                date = datetime.datetime.strptime(match.group(1), "%Y%m%d")
                if last_date is None or last_date < date:
                    last_file_path = file_path
                    last_date = date
                    last_is_gz = match.group(2) is not None

        if last_file_path is not None:
            log_info = LogInfo(last_file_path, last_date, last_is_gz)
    else:
        logging.info('Log dir %s not found', log_dir)

    return log_info


def make_report_file_path(config, log_info):
    template_file_path = pathlib.Path(config.REPORT_TEMPLATE)
    report_file_date = log_info.date.strftime('%Y.%m.%d')
    report_file_name = template_file_path.stem + '-' + report_file_date + template_file_path.suffix
    return pathlib.Path(config.REPORT_DIR) / report_file_name


def parse_log(config, log_info):
    open_func = gzip.open if log_info.is_gz else open
    with open_func(str(log_info.file_path), 'rt') as log_file:
        line_count = 0
        error_count = 0
        for line in log_file:
            line_count += 1
            match = re.fullmatch(LOG_PARSE_PATTERN, line)
            if match:
                yield LogRecord(match.group(1), float(match.group(2)))
            else:
                error_count += 1
        logging.info('Processed %d lines with %d errors', line_count, error_count)
        if line_count > 0 and error_count / line_count > config.PARSE_ERROR_RATE:
            raise Exception('Too many unparsed lines')


def collect_url_info(config, parse_log_it):
    info = {}
    count = 0
    time_sum = 0.0

    for log_record in parse_log_it:
        count += 1
        time_sum += log_record.process_time

        if log_record.url not in info:
            info[log_record.url] = []
        info[log_record.url].append(log_record.process_time)

    return UrlsInfo(info, count, time_sum)


def make_report_info(config, urls_info):
    report_info = []
    for url, process_times in urls_info.info.items():
        process_times.sort()

        report_record = {
            'url': url,
            'count': len(process_times),
            'time_med': process_times[len(process_times) // 2],
            'time_sum': 0.0,
            'time_max': None
        }

        for process_time in process_times:
            report_record['time_sum'] += process_time
            if report_record['time_max'] is None or report_record['time_max'] < process_time:
                report_record['time_max'] = process_time

        report_record['count_perc'] = report_record['count'] / urls_info.count * 100
        report_record['time_perc'] = report_record['time_sum'] / urls_info.time_sum * 100
        report_record['time_avg'] = report_record['time_sum'] / report_record['count']

        report_info.append(report_record)

    report_info.sort(key=lambda ri: ri['time_sum'], reverse=True)

    del report_info[config.REPORT_SIZE:]

    return report_info


def render_report(config, report_file_path, report_info):
    table_json = json.dumps(report_info)
    template_file_path = pathlib.Path(config.REPORT_TEMPLATE)
    template = Template(template_file_path.read_text())
    tmp_report_file_path = report_file_path.with_suffix(report_file_path.suffix + '.tmp')
    try:
        tmp_report_file_path.write_text(template.safe_substitute(table_json=table_json))
        tmp_report_file_path.rename(report_file_path)
    finally:
        if tmp_report_file_path.is_file():
            tmp_report_file_path.unlink()


def main():
    config = prepare_environment()
    dump_config(config)

    log_info = find_last_log(config)
    logging.info('Last log file found: %s', log_info.file_path)

    report_file_path = make_report_file_path(config, log_info)
    if report_file_path.is_file():
        logging.info('Report exists: %s', report_file_path)
        return

    parse_log_it = parse_log(config, log_info)
    urls_info = collect_url_info(config, parse_log_it)
    report_info = make_report_info(config, urls_info)

    logging.info('Render report %s', report_file_path)
    render_report(config, report_file_path, report_info)


if __name__ == "__main__":
    try:
        main()
        logging.info('Script Finished')
    except Exception as e:
        logging.exception(e)
    except KeyboardInterrupt as e:
        logging.exception(e)
