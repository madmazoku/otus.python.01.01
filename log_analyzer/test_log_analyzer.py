#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import pathlib
import subprocess
import json
import datetime

import log_analyzer


class ScriptExecTest(unittest.TestCase):
    def test_script_exec(self):

        script_log_path = pathlib.Path('test') / 'log_analyzer.log'
        report_json_path = pathlib.Path('test') / 'report' / 'report-2017.06.30.json'

        if script_log_path.is_file():
            script_log_path.unlink()
        if report_json_path.is_file():
            report_json_path.unlink()

        cmd = './log_analyzer.py --config test/config.json'
        subprocess.run(cmd, shell=True, check=True)

        self.assertTrue(script_log_path.is_file())
        self.assertTrue(report_json_path.is_file())

        report_json = json.loads(report_json_path.read_text())

        self.assertEqual(report_json[0]['url'], '/api/v2/banner/26647998')
        self.assertEqual(report_json[0]['count'], 10)
        self.assertAlmostEqual(report_json[0]['time_sum'], 16.56)
        self.assertAlmostEqual(report_json[0]['time_avg'], 1.656)
        self.assertAlmostEqual(report_json[0]['time_max'], 3.342)
        self.assertAlmostEqual(report_json[0]['time_med'], 1.555)
        self.assertAlmostEqual(report_json[0]['count_perc'], 50)
        self.assertAlmostEqual(report_json[0]['time_perc'], 64.042076)

        script_log_path.unlink()
        report_json_path.unlink()


class ConfigTest(unittest.TestCase):
    def test_config_load(self):
        config = log_analyzer.Config('test/config.json')

        self.assertEqual(config.config_json_path, pathlib.Path('test/config.json'))

        self.assertDictEqual(
            config.config, {
                'REPORT_SIZE': 1,
                'REPORT_DIR': 'test/report',
                'REPORT_TEMPLATE': 'test/report.json',
                'LOG_DIR': 'test/log',
                'PARSE_ERROR_RATE': 0.5,
                'SCRIPT_LOG_PATH': 'test/log_analyzer.log'
            })

        self.assertEqual(config.REPORT_SIZE, 1)
        self.assertEqual(config.REPORT_DIR, 'test/report')
        self.assertEqual(config.REPORT_TEMPLATE, 'test/report.json')
        self.assertEqual(config.LOG_DIR, 'test/log')
        self.assertAlmostEqual(config.PARSE_ERROR_RATE, 0.5)
        self.assertEqual(config.SCRIPT_LOG_PATH, 'test/log_analyzer.log')


class ProcessingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = log_analyzer.Config('test/config.json')
        cls.log_info = log_analyzer.LogInfo(
            pathlib.Path('test/log/nginx-access-ui.log-20170630.gz'), datetime.datetime(2017, 6, 30), True)
        cls.parsed = [
            log_analyzer.LogRecord('/api/v2/banner/26647998', 2.714),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 3.342),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 0.894),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 1.555),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 1.24),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 1.726),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 1.093),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 2.195),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 0.539),
            log_analyzer.LogRecord('/api/v2/banner/26647998', 1.262),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 1.101),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 0.308),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 0.479),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 1.287),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 2.023),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 0.913),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 0.34),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 0.226),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 1.45),
            log_analyzer.LogRecord('/api/v2/banner/26619125', 1.171)
        ]
        cls.collected = log_analyzer.UrlsInfo({
            '/api/v2/banner/26619125': [1.101, 0.308, 0.479, 1.287, 2.023, 0.913, 0.34, 0.226, 1.45, 1.171],
            '/api/v2/banner/26647998': [2.714, 3.342, 0.894, 1.555, 1.24, 1.726, 1.093, 2.195, 0.539, 1.262]
        }, 20, 25.858)
        cls.report = [{
            'time_med': 1.555,
            'time_sum': 16.56,
            'count': 10,
            'count_perc': 50.0,
            'time_perc': 64.042076,
            'time_avg': 1.656,
            'url': '/api/v2/banner/26647998',
            'time_max': 3.342
        }]
        report_json_path = pathlib.Path('test/report/test_render_report.json')
        if report_json_path.is_file():
            report_json_path.unlink()

    @classmethod
    def tearDownClass(cls):
        report_json_path = pathlib.Path('test/report/test_render_report.json')
        if report_json_path.is_file():
            report_json_path.unlink()

    def test_find_last_log(self):
        log_info = log_analyzer.find_last_log(self.config)
        self.assertEqual(log_info, self.log_info)

    def test_make_report_file_path(self):
        report_file_path = log_analyzer.make_report_file_path(self.config, self.log_info)
        self.assertEqual(report_file_path, pathlib.Path('test/report/report-2017.06.30.json'))

    def test_parse_log(self):
        parsed = [x for x in log_analyzer.parse_log(self.config, self.log_info)]
        self.assertListEqual(parsed, self.parsed)

    def test_collect_url_info(self):
        collected = log_analyzer.collect_url_info(self.config, self.parsed)
        self.assertDictEqual(collected.info, self.collected.info)
        self.assertEqual(collected.count, self.collected.count)
        self.assertAlmostEqual(collected.time_sum, self.collected.time_sum)

    def test_make_report_info(self):
        report = log_analyzer.make_report_info(self.config, self.collected)
        self.assertEqual(len(report), len(self.report))
        self.assertAlmostEqual(report[0]['time_med'], self.report[0]['time_med'])
        self.assertAlmostEqual(report[0]['time_sum'], self.report[0]['time_sum'])
        self.assertEqual(report[0]['count'], self.report[0]['count'])
        self.assertAlmostEqual(report[0]['count_perc'], self.report[0]['count_perc'])
        self.assertAlmostEqual(report[0]['time_perc'], self.report[0]['time_perc'])
        self.assertAlmostEqual(report[0]['time_avg'], self.report[0]['time_avg'])
        self.assertEqual(report[0]['url'], self.report[0]['url'])
        self.assertAlmostEqual(report[0]['time_max'], self.report[0]['time_max'])

    def test_render_report(self):
        report_json_path = pathlib.Path('test/report/test_render_report.json')
        log_analyzer.render_report(self.config, report_json_path, self.report)
        self.assertTrue(report_json_path.is_file())
        report_json = json.loads(report_json_path.read_text())
        self.assertListEqual(report_json, self.report)
        report_json_path.unlink()


if __name__ == '__main__':
    unittest.main()
