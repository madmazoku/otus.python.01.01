#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import pathlib
import subprocess
import json


def setUpModule():
    pass


def tearDownModule():
    pass


class ScriptExecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_files = {
            'log_analyzer':
            pathlib.Path('test') / 'log_analyzer.log',
            'log':
            pathlib.Path('test') / 'tmp' / 'nginx-access-ui.log',
            'url':
            pathlib.Path('test') / 'tmp' / 'url.tsv',
            'url_error':
            pathlib.Path('test') / 'tmp' / 'url.tsv.err',
            'collect':
            pathlib.Path('test') / 'tmp' / 'collect.tsv',
            'stat':
            pathlib.Path('test') / 'tmp' / 'stat.tsv',
            'report':
            pathlib.Path('test') / 'tmp' / 'report.tsv',
            'report_html':
            pathlib.Path('test') / 'report' / 'report-2017.06.30.html'
        }
        cmd = './log_analyzer.py --config test/config.json 2> /dev/null'
        subprocess.run(cmd, shell=True, check=True)

    @classmethod
    def tearDownClass(cls):
        for f in cls.expected_files:
            if cls.expected_files[f].is_file():
                cls.expected_files[f].unlink()
        cls.expected_files = None

    def test_files_exists(self):
        for f in self.expected_files:
            self.assertTrue(self.expected_files[f].is_file())

    def test_report_html(self):
        report_html = None
        with open(str(self.expected_files['report_html'])) as file:
            report_html = json.load(file)
        self.assertListEqual(report_html, [{
            "url": "/api/v2/banner/26647998",
            "count": 10,
            "time_sum": 16.560000000000002,
            "time_avg": 1.6560000000000001,
            "time_max": 3.342,
            "time_med": 1.555,
            "count_perc": 50.0,
            "time_perc": 64.04207595328333
        }])

    def test_log_tsv(self):
        count = 0
        with open(str(self.expected_files['log'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 22)

    def test_url_tsv(self):
        count = 0
        with open(str(self.expected_files['url'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 20)

    def test_url_tsv_err(self):
        count = 0
        with open(str(self.expected_files['url_error'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 2)

    def test_collect_tsv(self):
        count = 0
        with open(str(self.expected_files['collect'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 20)

    def test_stat_tsv(self):
        count = 0
        with open(str(self.expected_files['stat'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 2)

    def test_report_tsv(self):
        count = 0
        with open(str(self.expected_files['report'])) as url_error:
            for line in url_error:
                count += 1
        self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main()
