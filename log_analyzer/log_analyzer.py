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
import tempfile
import gzip
import subprocess
import time
import shutil

DEFAULT_CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "REPORT_TEMPLATE": "./report.html",
    "LOG_DIR": "./log",
    "PARSE_ERROR_RATIO": 0.01,
    "MEDIAN_BAG_SIZE": 1000
}
DEFAULT_CONFIG_JSON_PATH = './config.json'

# LOG_PARSE_PATTERN = re.compile('.+"(?:GET|HEAD|POST|PUT|DELETE|CONNECT|OPTIONS|TRACE|PATCH)\\s([^\\s]+)\\s.+\\s([\\d\\.]+)\\n')
LOG_PARSE_PATTERN = re.compile(
    '.+?\\]\\s"[^\\s"]+\\s([^\\s"]+)\\s.+\\s([\\d\\.]+)\\n')
URL_PARSE_PATTERN = re.compile('([^\\t]+)\\t([\\d\\.]+)\n')

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s', level='INFO')


class LAE(Exception):
    """Base class for exceptions in this module."""
    pass


class Progress:
    def __init__(self):
        self.stat = {}
        self.start_time = time.time()
        self.prev_time = self.start_time
        self.count = 0

    def inc(self, stat_name, stat_val=1):
        if stat_name not in self.stat:
            self.stat[stat_name] = 0
        self.stat[stat_name] += stat_val

    def val(self, stat_name):
        return self.stat[stat_name] if stat_name in self.stat else None

    def tick(self):
        self.count += 1

    def report(self, message=None):
        curr_time = time.time()
        dt = curr_time - self.prev_time
        dtf = curr_time - self.start_time
        if message is not None or (dtf < 10 and dt >= 1) or (
                dtf < 30 and dt >= 5) or (dtf < 60 and dt >= 10) or (
                    dtf < 600 and dt >= 30) or dt >= 60:
            spd = 0 if dtf == 0 else (self.count / dtf)
            report = '[{:10.2f}] count: {:10d}; speed: {:10.2f}'.format(
                dtf, self.count, spd)
            for s in self.stat:
                report += '; ' + '{:s}: {:10d}'.format(s, self.stat[s])
            if message is not None:
                report += '; ' + message
            logging.info(report)
            self.prev_time = curr_time


def parse_config():
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
        return None
    except json.decoder.JSONDecodeError as e:
        logging.critical("Can't parse configuration file json %s. %s",
                         config_json_path, e)
        return None

    config.update(config_json)

    logging.info("CONFIG: %s", config_json_path)
    for k in sorted(config):
        v = config[k]
        logging.info('\t%s: %s', k, v)

    return config


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


def get_url_info(config, log_path, tmp_dir_name):
    url_file_name = pathlib.Path(tmp_dir_name) / 'url.tsv'
    logging.info('Extract data from %s to %s', log_path, url_file_name)
    progress = Progress()
    lines = 0
    errors = 0
    with gzip.open(str(log_path), 'rt') as log_file:
        with open(str(url_file_name), 'w') as url_file:
            with open(str(url_file_name) + '.err', 'w') as err_url_file:
                for line in log_file:
                    progress.tick()
                    progress.report()
                    match = re.fullmatch(LOG_PARSE_PATTERN, line)
                    if match:
                        print('{:s}\t{:s}'.format(match.group(1), match.group(2)), file=url_file)
                    else:
                        print(line, file=err_url_file, end='')
                        progress.inc('errors', 1)
    progress.report('Finished')
    if progress.count == 0:
        logging.warning('No lines in the log file {!s}'.format(log_path))
    if progress.val('errors') and progress.val('errors') / progress.count > config['PARSE_ERROR_RATIO']:
        msg = 'Too many unparsed lines in {!s}'.format(log_path)
        logging.critical(msg)
        raise LAE(msg)
    return url_file_name


def collect_urls(config, url_file_name, tmp_dir_name):
    collect_file_name = pathlib.Path(tmp_dir_name) / 'collect.tsv'
    logging.info('Sort data from %s to %s', url_file_name, collect_file_name)
    cmd = 'LC_ALL=C sort {!s} -k 1 -o {!s}'.format(url_file_name, collect_file_name)
    logging.info('\t%s', cmd)
    try:
        result = subprocess.run(cmd, shell = True, check = True)
    except subprocess.CalledProcessError:
        logging.critical('Can\'t sort url file %s', url_file_name)
        raise
    logging.info('\tFinished')
    return collect_file_name


class StatCollector:
    def __init__(self, config):
        self.config = config
        self.storage = []
        self.new()

    def new(self):
        del self.storage[:]
        self.skip = 1
        self.count = 0
        self.time_avg = 0
        self.time_sum = 0
        self.time_max = None

    def add(self, process_time):
        if self.count % self.skip == 0:
            if len(self.storage) >= self.config['MEDIAN_BAG_SIZE'] * 2:
                for i in range(len(self.storage), 0, -2):
                    del self.storage[i - 1]
                self.skip *= 2
            self.storage.append(process_time)

        self.count += 1
        self.time_avg = (
            self.count -
            1) / self.count * self.time_avg + process_time / self.count
        self.time_sum += process_time

        if self.time_max is None or self.time_max < process_time:
            self.time_max = process_time

    def finish(self, url):
        if self.count > 0:
            self.storage.sort()
            median = self.storage[len(self.storage) // 2]
            stat = {
                'url': url,
                'count': self.count,
                'time_sum': self.time_sum,
                'time_avg': self.time_avg,
                'time_max': self.time_max,
                'time_med': median
            }
            self.new()
            return stat
        return


class ReportCollector:
    def __init__(self, config):
        self.config = config
        self.storage = []

    def add(self, stat):
        idx = None
        for i in range(0, len(self.storage)):
            if stat['time_sum'] > self.storage[i]['time_sum']:
                idx = i
                break
        if idx is None:
            self.storage.append(stat)
        else:
            self.storage.insert(idx, stat)

        if len(self.storage) == self.config['REPORT_SIZE']:
            del self.storage[-1]

    def finish(self, stat_all):
        for stat in self.storage:
            stat['count_perc'] = stat['count'] * 100 / stat_all['count']
            stat['time_perc'] = stat['time_sum'] * 100 / stat_all['time_sum']
        storage = self.storage
        self.storage = []
        return storage


def get_report_info(config, collect_file_name, tmp_dir_name):
    stat_file_name = pathlib.Path(tmp_dir_name) / 'stat.tsv'
    logging.info('Extract stat data from %s to %s', collect_file_name,
                 stat_file_name)
    stat_all_collector = StatCollector(config)
    report_collector = ReportCollector(config)
    progress = Progress()
    report = None
    with open(str(collect_file_name), 'rt') as collect_file:
        with open(str(stat_file_name), 'w') as stat_file:
            url = None
            stat_collector = StatCollector(config)
            for line in collect_file:
                progress.tick()
                progress.report()
                match = re.fullmatch(URL_PARSE_PATTERN, line)
                if match is None:
                    msg = 'Invalid line "{:s}" in {!s}'.format(
                        line, collect_file_name)
                    logging.critical(msg)
                    raise LAE(msg)
                if url is None or url != match.group(1):
                    if url is not None:
                        stat = stat_collector.finish(url)
                        report_collector.add(stat)
                        print(
                            '{:s}\t{:d}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}'.
                            format(url, stat['count'], stat['time_sum'],
                                   stat['time_avg'], stat['time_max'],
                                   stat['time_med']),
                            file=stat_file)
                    url = match.group(1)
                    progress.inc('uniq')
                stat_collector.add(float(match.group(2)))
                stat_all_collector.add(float(match.group(2)))
            if url is not None:
                stat = stat_collector.finish(url)
                report_collector.add(stat)
                print(
                    '{:s}\t{:d}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}'.format(
                        url, stat['count'], stat['time_sum'], stat['time_avg'],
                        stat['time_max'], stat['time_med']),
                    file=stat_file)
            stat_all = stat_all_collector.finish('TOTAL')
            report = report_collector.finish(stat_all)
    progress.report('Finished')

    report_file_name = pathlib.Path(tmp_dir_name) / 'report.tsv'
    with open(str(report_file_name), 'w') as report_file:
        for r in report:
            print(
                '{:s}\t{:d}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}'.
                format(r['url'], r['count'], r['count_perc'], r['time_sum'],
                       r['time_perc'], r['time_avg'], r['time_max'],
                       r['time_med']),
                file=report_file)

    return report


def store_report(config, report, date):
    report_file_name = pathlib.Path(
        config['REPORT_DIR']) / ('report-' + date + '.html')
    logging.info('Store report to %s', report_file_name)
    tmp_report_file_name = pathlib.Path(
        config['TMP_DIR']) / ('report-' + date + '.html')
    table_json = json.dumps(report)
    with open(config['REPORT_TEMPLATE'], 'rt') as report_template:
        with open(str(tmp_report_file_name), 'w') as report_file:
            for line in report_template:
                print(
                    line.replace('$table_json', table_json),
                    file=report_file,
                    end='')
    shutil.move(str(tmp_report_file_name), str(report_file_name))


def main():
    config = parse_config()
    if config is None:
        return

    try:
        last_log_path, last_log_date = last_log(config['LOG_DIR'])
    except FileNotFoundError as e:
        logging.critical("LOG_DIR %s absent. %s", config['LOG_DIR'], e)
        return

    if last_log_date is None:
        logging.warning('No logs found')
        return

    if is_log_date_reported(config['REPORT_DIR'], last_log_date):
        logging.warning('Last log %s already reported', last_log_path)
        return

    logging.info('Make report for date %s. %s', last_log_date, last_log_path)

    tmp_dir = None
    tmp_dir_name = None
    if 'TMP_DIR' in config:
        tmp_dir_name = config['TMP_DIR']
    else:
        tmp_dir = tempfile.TemporaryDirectory()
        tmp_dir_name = tmp_dir.name

    url_file_name = get_url_info(config, last_log_path, tmp_dir_name)
    collect_file_name = collect_urls(config, url_file_name, tmp_dir_name)
    report = get_report_info(config, collect_file_name, tmp_dir_name)

    store_report(config, report, last_log_date)


if __name__ == "__main__":
    main()
