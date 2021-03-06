============
log_analyzer
============

Introduction
============

log_analyzer.py scrip is intended to parse nginx logs with specific format
and collect statistic from it to generate report html based on template file.

.. contents::


Usage
=====

Options

.. code-block:: 

    ./log_analyzer.py [--config CONFIG_JSON_PATH]

        nginx log analyzer

    optional argument:

        --config    path to config file in json format, like './config.json' 
                    which is default value

Example
-------

Execute script:

.. code-block:: 

    ./log_analyzer.py

Execute tests:

.. code-block:: 

    ./test_log_analyzer.py


Log format
==========

nginx

.. code-block:: 

    '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
    '$status $body_bytes_sent "$http_referer" '
    '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" '
    '"$http_X_RB_USER" '
    '$request_time'

Template format
===============

It is expected, that template file have substring ``$table_json`` which
will be replaced with result table in json format.

Result table example

.. code-block:: json

    [
      {
        "url": "/api/v2/internal/html5/phantomjs/queue/?wait=1m",
        "count": 2767,
        "time_sum": 174306.3519999998,
        "time_avg": 62.99470617997834,
        "time_max": 9843.569,
        "time_med": 60.073,
        "count_perc": 0.10586581555703324,
        "time_perc": 9.04290096479376
      },
      {
        "url": "/api/v2/internal/gpmd_plan_report/queue/?wait=1m&worker=5",
        "count": 1410,
        "time_sum": 94618.86400000018,
        "time_avg": 67.10557730496446,
        "time_max": 9853.373,
        "time_med": 60.124,
        "count_perc": 0.05394680156682938,
        "time_perc": 4.908765554070526
      }
    ]

Config format
=============

Default config

.. code-block:: json

    {
        "REPORT_SIZE": 1000,
        "REPORT_DIR": "./reports",
        "REPORT_TEMPLATE": "./report.html",
        "LOG_DIR": "./log",
        "PARSE_ERROR_RATE": 0.01,
        "SCRIPT_LOG_PATH": null
    }


Default path to config is ``./config.json``

Default config will be updated from config json file.

``REPORT_SIZE``
    How much urls will be presented in result table.

``REPORT_DIR``
    Path to directory to contain report html files.

``REPORT_TEMPLATE``
    Path to template file.

``LOG_DIR``
    Path to directory which contain log files to be processed

    Log file name must conform format: ``nginx-access-ui.log-YYYYMMDD`` and may
    be compressed by gzip in which case it will have ``.gz`` extention 
    additionally

``PARSE_ERROR_RATE``
    Allowed share size for unparsed lines in log

``SCRIPT_LOG_PATH``
    Where to store script logging, in addition to STDERR. Do not write to file
    if null.
