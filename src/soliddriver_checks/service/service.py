#!/usr/bin/env python3

from threading import Lock, Thread
from bottle import get, run, response
from ..api.analysis import kms_to_json
from ..version import __VERSION__
import os
import json
import logging
from time import sleep


class KMInfo:
    def __init__(self, interval):
        self._data_lock = Lock()
        self._info = json.dumps([])
        self._interval = interval
        t = Thread(target=self._async_refresh_data)
        t.start()

    @property
    def data(self):
        info = ""
        with self._data_lock:
            info = self._info
        return info

    def _async_refresh_data(self):
        while True:
            self._refresh_data()
            sleep(self._interval * 60 * 60)

    def _refresh_data(self):
        logging.info("start to refresh data...")
        new_data = kms_to_json()
        with self._data_lock:
            self._info = new_data
        logging.info("data refreshing is completed!")


def run_as_service(host="0.0.0.0", port=8080):
    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
    logging.info("soliddriver-checks-service version: %s" % __VERSION__)

    interval = os.getenv("REFRESH_INTERVAL")
    interval = int(interval) if interval is not None else 1
    logging.info("refresh interval: %s hour(s)" % interval)

    global kms
    kms = KMInfo(interval)

    run(host=host, port=port, quiet=True)


@get('/kms_info')
def kms_info():
    response.content_type = 'application/json'
    info = kms.data
    logging.info("GET /kms_info HTTP/1.1")

    return info


if __name__ == "__main__":
    run_as_service()
