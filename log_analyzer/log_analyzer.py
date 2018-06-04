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

DEFAULT_CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "REPORT_TEMPLATE": "./report.html",
    "LOG_DIR": "./log",
    "PARSE_ERROR_RATE": 0.01,
    "MEDIAN_BAG_SIZE": 1000,
    "MEDIAN_BAG_SAMPLE_RATE": 0.75,
    "TMP_DIR": None,
    "SCRIPT_LOG_PATH": None,
    "DEBUG": False
}
DEFAULT_CONFIG_JSON_PATH = './config.json'

# LOG_PARSE_PATTERN = re.compile('.+"(?:GET|HEAD|POST|PUT|DELETE|CONNECT|OPTIONS|TRACE|PATCH)\\s([^\\s]+)\\s.+\\s([\\d\\.]+)\\n')
LOG_NAME_PATTERN = re.compile('nginx-access-ui.log-(\\d{8})(\\.gz)?')
LOG_PARSE_PATTERN = re.compile(
    '.+?\\]\\s"[^\\s"]+\\s([^\\s"]+)\\s.+\\s([\\d\\.]+)\\n')


class Progress:
    """Class is intended to log progress for some lengthly activity"""

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


def parse_args():
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument(
        "--config", help="path to configuration file in json format", type=str)
    args = args_parser.parse_args()
    return args


def parse_config(config_json_path):
    """Load config json file and merge it with default config"""
    if config_json_path is None:
        config_json_path = DEFAULT_CONFIG_JSON_PATH

    config_json = None
    with open(config_json_path) as config_json_file:
        config_json = json.load(config_json_file)

    config = {}
    config.update(DEFAULT_CONFIG)
    config.update(config_json)

    return config, config_json_path


def add_log_file(script_log_path):
    """add file to write log"""
    script_log_dir = pathlib.Path(script_log_path).parent
    if not script_log_dir.is_dir():
        script_log_dir.mkdir(parent=True, exist_ok=True)
    logging.getLogger().addHandler(logging.FileHandler(script_log_path))


def dump_config(config, config_json_path):
    logging.info("Scrip started")
    logging.info("CONFIG: %s", config_json_path)
    for k in sorted(config):
        v = config[k]
        logging.info('\t%s: %s', k, v)


def setup():
    """Prepare config and setup environment"""
    logging.basicConfig(
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S',
        level='INFO')

    args = parse_args()

    config, config_json_path = parse_config(args.config)
    if config['SCRIPT_LOG_PATH'] is not None:
        add_log_file(config['SCRIPT_LOG_PATH'])

    dump_config(config, config_json_path)

    return config


def get_last_log(config):
    log_file_name = None
    log_date = None
    log_is_gz = None

    log_dir = pathlib.Path(config['LOG_DIR'])
    if log_dir.is_dir():
        for file_name in log_dir.iterdir():
            if not file_name.is_file():
                continue
            match = re.fullmatch(LOG_NAME_PATTERN, file_name.name)
            if match and (log_date is None or log_date < match.group(1)):
                log_file_name = file_name
                log_date = match.group(1)
                log_is_gz = match.group(2) is not None

        if log_date:
            log_date = re.sub('(\\d{4})(\\d\\d)(\\d\\d)', '\\1.\\2.\\3',
                              log_date)
    else:
        logging.info('Log dir %s not found', log_dir)

    return log_file_name, log_is_gz, log_date


def make_report_file_name(config, date):
    report_dir = pathlib.Path(config['REPORT_DIR'])
    if not report_dir.is_dir():
        logging.info('Report dir %s not found. Create it.', report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
    return pathlib.Path(config['REPORT_DIR']) / 'report-{:s}.html'.format(date)


def make_tmp_dir_name(config):
    tmp_dir = None
    tmp_dir_name = None
    if config['TMP_DIR'] is None:
        tmp_dir = tempfile.TemporaryDirectory()
        tmp_dir_name = pathlib.Path(tmp_dir.name)
    else:
        tmp_dir_name = pathlib.Path(config['TMP_DIR'])
        if not tmp_dir_name.is_dir():
            logging.info('Tmp dir %s not found. Create it.', tmp_dir_name)
            tmp_dir_name.mkdir(parents=True, exist_ok=True)
    logging.info('Tmp dir %s will be used.', tmp_dir_name)
    return tmp_dir, tmp_dir_name


def decompress(config, log_file_name, tmp_dir_name):
    tmp_log_file_name = pathlib.Path(tmp_dir_name) / 'nginx-access-ui.log'
    logging.info('Uncompress log from %s to %s', log_file_name,
                 tmp_log_file_name)
    cmd = 'zcat {!s} > {!s}'.format(log_file_name, tmp_log_file_name)
    logging.info('\t%s', cmd)
    try:
        result = subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        logging.error('Can\'t uncompress log file %s', log_file_name)
        raise
    logging.info('\tFinished')
    return tmp_log_file_name


def get_url_info(config, log_path, tmp_dir_name):
    url_file_name = pathlib.Path(tmp_dir_name) / 'url.tsv'
    logging.info('Extract data from %s to %s', log_path, url_file_name)
    progress = Progress()
    with open(str(log_path), 'rt') as log_file, open(str(url_file_name),
                                                     'w') as url_file:
        err_url_file = None
        if config['DEBUG']:
            err_url_file = open(str(url_file_name) + '.err', 'w')

        tsv_writer = csv.writer(
            url_file, delimiter='\t', quoting=csv.QUOTE_NONE)
        for line in log_file:
            progress.tick()
            progress.report()
            match = re.fullmatch(LOG_PARSE_PATTERN, line)
            if match:
                tsv_writer.writerow(
                    [match.group(1),
                     match.group(2),
                     random.random()])
            else:
                if err_url_file:
                    print(line, file=err_url_file, end='')
                progress.inc('errors', 1)

        if err_url_file is not None:
            err_url_file.close()

    progress.report('Finished')
    if progress.count == 0:
        logging.info('No lines in the log file {!s}'.format(log_path))
    if progress.val('errors') and progress.val(
            'errors') / progress.count > config['PARSE_ERROR_RATE']:
        msg = 'Too many unparsed lines in {!s}'.format(log_path)
        logging.error(msg)
        raise Exception(msg)

    return url_file_name


def collect_urls(config, url_file_name, tmp_dir_name):
    collect_file_name = pathlib.Path(tmp_dir_name) / 'collect.tsv'
    logging.info('Sort data from %s to %s', url_file_name, collect_file_name)
    cmd = 'LC_ALL=C sort {!s} -k 1 -o {!s}'.format(url_file_name,
                                                   collect_file_name)
    logging.info('\t%s', cmd)
    try:
        result = subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        logging.error('Can\'t sort url file %s', url_file_name)
        raise
    logging.info('\tFinished')
    return collect_file_name


class StatCollector:
    """Class is intended to aggregate statistics for current url"""

    def __init__(self, config):
        self.config = config
        self.median_bag = []
        self.median_bag_upper_size = self.config['MEDIAN_BAG_SIZE'] / self.config['MEDIAN_BAG_SAMPLE_RATE']
        self.new()

    def new(self):
        """Data for new url will be passed after call"""
        del self.median_bag[:]
        self.rate = 1
        self.count = 0
        self.time_avg = 0
        self.time_sum = 0
        self.time_max = None

    def add(self, process_time, rnd):
        """Add next processing time and random value for current url"""
        if rnd < self.rate:
            self.median_bag.append({'process_time': process_time, 'rnd': rnd})

        while len(self.median_bag) > self.median_bag_upper_size:
            self.rate *= self.config['MEDIAN_BAG_SAMPLE_RATE']
            for i in range(len(self.median_bag), 0, -1):
                if self.median_bag[i - 1]['rnd'] >= self.rate:
                    del self.median_bag[i - 1]

        self.count += 1
        self.time_avg = (
            self.count -
            1) / self.count * self.time_avg + process_time / self.count
        self.time_sum += process_time

        if self.time_max is None or self.time_max < process_time:
            self.time_max = process_time

    def finish(self, url):
        """Calculate current url statisctics and return dictionary with it"""
        if self.count > 0:
            self.median_bag.sort(key=lambda s: s['process_time'])
            median = self.median_bag[len(self.median_bag) // 2]['process_time']
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
    """Class intended to find top N urls by time_sum"""

    def __init__(self, config, stat_file_name):
        self.config = config
        self.storage = []

        self.stat_file = None
        self.tsv_writer = None
        if stat_file_name is not None:
            logging.info("Create stat file: %s", stat_file_name)
            self.stat_file = open(str(stat_file_name), 'w')
            self.tsv_writer = csv.writer(
                self.stat_file, delimiter='\t', quoting=csv.QUOTE_NONE)

    def __del__(self):
        if self.stat_file is not None:
            self.stat_file.close()

    def add(self, stat):
        if self.tsv_writer is not None:
            self.tsv_writer.writerow([
                stat['url'], stat['count'], stat['time_sum'], stat['time_avg'],
                stat['time_max'], stat['time_med']
            ])

        idx = None
        for i in range(0, len(self.storage)):
            if stat['time_sum'] > self.storage[i]['time_sum']:
                idx = i
                break
        if idx is None:
            self.storage.append(stat)
        else:
            self.storage.insert(idx, stat)

        if len(self.storage) > self.config['REPORT_SIZE']:
            del self.storage[-1]

    def finish(self, count, time_sum):
        """Return top N statiscis with added percentages"""
        for stat in self.storage:
            stat['count_perc'] = stat['count'] * 100 / count
            stat['time_perc'] = stat['time_sum'] * 100 / time_sum
        return self.storage


def get_report_info(config, collect_file_name, tmp_dir_name):
    stat_file_name = None
    if config['DEBUG']:
        stat_file_name = pathlib.Path(tmp_dir_name) / 'stat.tsv'
        logging.info('Extract stat data from %s to %s', collect_file_name,
                     stat_file_name)
    else:
        logging.info('Extract stat data from %s', collect_file_name)

    report = None
    with open(str(collect_file_name), 'rt') as collect_file:
        count = 0
        time_sum = 0
        progress = Progress()

        curr_url = None
        stat_collector = StatCollector(config)
        tsv_reader = csv.reader(
            collect_file, delimiter='\t', quoting=csv.QUOTE_NONE)

        report_collector = ReportCollector(config, stat_file_name)

        for row in tsv_reader:
            progress.tick()
            progress.report()

            url = row[0]
            process_time = float(row[1])
            rnd = float(row[2])

            if curr_url is None or curr_url != url:
                if curr_url is not None:
                    stat = stat_collector.finish(curr_url)
                    report_collector.add(stat)
                curr_url = url
                progress.inc('uniq')

            stat_collector.add(process_time, rnd)
            count += 1
            time_sum += process_time

        if curr_url is not None:
            stat = stat_collector.finish(curr_url)
            report_collector.add(stat)

        report = report_collector.finish(count, time_sum)
        progress.report('Finished')

    return report


def store_report_tsv(config, report, tmp_dir_name):
    report_file_name = pathlib.Path(tmp_dir_name) / 'report.tsv'
    logging.info('Store report stat to file %s', report_file_name)
    with open(str(report_file_name), 'w') as report_file:
        tsv_report_writer = csv.writer(
            report_file, delimiter='\t', quoting=csv.QUOTE_NONE)
        for r in report:
            tsv_report_writer.writerow([
                r['url'], r['count'], r['count_perc'], r['time_sum'],
                r['time_perc'], r['time_avg'], r['time_max'], r['time_med']
            ])


def store_report(config, report, date, tmp_dir_name):
    tmp_report_file_name = pathlib.Path(tmp_dir_name) / (
        'report-' + date + '.html')
    logging.info('Store report to %s', tmp_report_file_name)
    table_json = json.dumps(report)
    with open(config['REPORT_TEMPLATE'], 'rt') as report_template:
        with open(str(tmp_report_file_name), 'w') as report_file:
            for line in report_template:
                print(
                    line.replace('$table_json', table_json),
                    file=report_file,
                    end='')
    return tmp_report_file_name


def main():
    config = setup()

    log_file_name, log_is_gz, log_date = get_last_log(config)

    if log_file_name is None:
        logging.info('No logs found')
        return

    report_file_name = make_report_file_name(config, log_date)
    if report_file_name.is_file():
        logging.info('Last log %s already reported to %s', log_file_name,
                     report_file_name)
        return

    logging.info('Report log %s to %s', log_file_name, report_file_name)

    tmp_dir, tmp_dir_name = make_tmp_dir_name(config)

    if log_is_gz:
        log_file_name = decompress(config, log_file_name, tmp_dir_name)

    url_file_name = get_url_info(config, log_file_name, tmp_dir_name)

    collect_file_name = collect_urls(config, url_file_name, tmp_dir_name)

    report = get_report_info(config, collect_file_name, tmp_dir_name)

    if config['DEBUG']:
        store_report_tsv(config, report, tmp_dir_name)

    tmp_report_file_name = store_report(config, report, log_date, tmp_dir_name)

    logging.info('Move report from %s to %s', tmp_report_file_name,
                 report_file_name)
    shutil.move(str(tmp_report_file_name), str(report_file_name))

    return


if __name__ == "__main__":
    try:
        main()
        logging.info('Script Finished')
    except Exception as e:
        logging.exception(e)
    except KeyboardInterrupt as e:
        logging.exception(e)
