#!/usr/bin/env python3

from threading import Lock, Thread, Timer
from bottle import route, run, response
from ..api.analysis import kms_to_json
import os
import json


class KMInfo:
    def __init__(self, interval):
        self._data_lock = Lock()
        self._info = json.dumps([])
        self._interval = interval
        self._refresh_data()
        t = Thread(self._async_refresh_data)
        t.run()

    @property
    def data(self):
        with self._data_lock:
            data = self._info
            return data

    def _async_refresh_data(self):
        while True:
            t = Timer(self._interval * 60 * 60, self._refresh_data)
            t.start()

    def _refresh_data(self):
        new_data = kms_to_json()
        with self._data_lock:
            self._info = new_data


def run_as_service(host="0.0.0.0", port=8080):
    run(host=host, port=port)


@route('/kms_info')
def kms_info():
    response.content_type = 'application/json'
    info = kms.data

    return info


if __name__ == "__main__":
    interval = os.getenv("REFRESH_INTERVAL")
    interval = interval if interval is not None else 1
    print("refresh interval: %s" % interval)
    global kms
    kms = KMInfo(interval)

    run_as_service()
