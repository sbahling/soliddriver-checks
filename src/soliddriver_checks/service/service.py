#!/usr/bin/env python3

from threading import Lock, Thread
from bottle import get, run, response
from ..api.analysis import kms_to_json
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
        logger.info("start to refresh data...")
        new_data = kms_to_json()
        with self._data_lock:
            self._info = new_data
        logger.info("refreshing data is completed!")


def run_as_service(host="0.0.0.0", port=8080):
    global logger
    logger = logging.getLogger("soliddriver-checks-service")
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s : %(name)s : %(levelname)s : %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    interval = os.getenv("REFRESH_INTERVAL")
    interval = interval if interval is not None else 1
    logger.info("refresh interval: %s hour(s)" % interval)
    
    global kms
    kms = KMInfo(interval)

    run(host=host, port=port)


@get('/kms_info')
def kms_info():
    response.content_type = 'application/json'
    info = kms.data

    return info


if __name__ == "__main__":
    run_as_service()
