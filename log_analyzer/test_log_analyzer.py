#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import pathlib
import subprocess
import json


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

        report_json = None
        with open(str(report_json_path)) as file:
            report_json = json.load(file)

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


if __name__ == '__main__':
    unittest.main()
