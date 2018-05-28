#!/usr/bin/env python
# -*- coding: utf-8 -*-

# log_format ui_short '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER"'
#                     '$request_time';

import argparse
import json
import logging
import copy
import pathlib
import re

DEFAULT_CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log"
}
DEFAULT_CONFIG_JSON_PATH = './config.json'

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s', level='INFO')


def last_log(directory):
    last_log_path = None
    last_log_date = None

    for path in pathlib.Path(directory).iterdir():
        if not path.is_file():
            continue
        match = re.fullmatch('nginx-access-ui.log-(\\d{8})\\.gz', path.name)
        if match and (last_log_date is None or last_log_date < match.group(1)):
            last_log_path = path
            last_log_date = match.group(1)
    if last_log_date:
        last_log_date = re.sub('(\\d{4})(\\d\\d)(\\d\\d)', '\\1.\\2.\\3',
                               last_log_date)
    return last_log_path, last_log_date


def is_log_date_reported(directory, log_date):
    for path in pathlib.Path(directory).iterdir():
        if not path.is_file():
            continue
        match = re.fullmatch('report-(\\d{4}\\.\\d\\d\\.\\d\\d)\\.html',
                             path.name)
        if match and (log_date == match.group(1)):
            return True
    return False


def main():
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument(
        "--config", help="path to configuration file in json format", type=str)
    args = args_parser.parse_args()

    config = copy.copy(DEFAULT_CONFIG)
    config_json_path = DEFAULT_CONFIG_JSON_PATH if args.config is None else args.config

    config_json = None
    try:
        with open(config_json_path) as config_json_file:
            config_json = json.load(config_json_file)
    except FileNotFoundError as e:
        logging.critical("Configuration file not found at %s. %s",
                         config_json_path, e)
        return
    except json.decoder.JSONDecodeError as e:
        logging.critical("Can't parse configuration file json %s. %s",
                         config_json_path, e)
        return

    config.update(config_json)

    logging.info("CONFIG: %s", config_json_path)
    for k in sorted(config):
        v = config[k]
        logging.info('\t%s: %s', k, v)

    try:
        last_log_path, last_log_date = last_log(config['LOG_DIR'])
    except FileNotFoundError as e:
        logging.critical("LOG_DIR %s absent. %s", config['LOG_DIR'], e)
        return

    if last_log_date is None:
        logging.warn('No logs found')
        return

    if is_log_date_reported(config['REPORT_DIR'], last_log_date):
        logging.warn('Last log %s already reported', last_log_path)
        return

    logging.info('Make report for date %s. %s', last_log_date, last_log_path)


if __name__ == "__main__":
    main()
