import urllib.request
import requests
from requests_html import HTMLSession
import re
import datetime
from pathlib import Path
import os


def getDate():
    date = datetime.datetime.now()
    currDate = date.strftime("%d-%b-%Y")
    
    return currDate

def saveFile(os_version, url, path):
    urllib.request.urlretrieve(url, os.path.join(path, Path(url).name))

def downloadRPMs(os_version, url, date):
    try:
        session = HTMLSession()
        response = session.get(url_sle12_sp4)
        links = response.html.absolute_links
        Path(os.path.join(date, os_version)).mkdir(parents=True, exist_ok=True)
        rpmlinks = []
        for link in links:
            m = re.search('.rpm$', link)
            if (m != None):
                rpmlinks.append(link)
                saveFile(os_version, link, os.path.join(date, os_version))
                print(link + "  is downloaded")

    except requests.exceptions.RequestException as e:
        print(e)

if __name__ == "__main__":
    base_url = 'https://linux.lenovo.com/yum/latest/repos/'

    sle12_sp4 = 'SLES12SP4'
    sle12_sp5 = 'SLES12SP5'
    sle15_sp1 = 'SLES15SP1'
    sle15_sp2 = 'SLES15SP2'
    url_sle12_sp4 = base_url + sle12_sp4
    url_sle12_sp5 = base_url + sle12_sp5
    url_sle15_sp1 = base_url + sle15_sp1
    url_sle15_sp2 = base_url + sle15_sp2

    date = getDate()
    downloadRPMs(sle12_sp4, url_sle12_sp4, date)
    downloadRPMs(sle12_sp5, url_sle12_sp5, date)
    downloadRPMs(sle15_sp1, url_sle15_sp1, date)
    downloadRPMs(sle15_sp2, url_sle15_sp2, date)