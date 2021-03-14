import subprocess
from pathlib import Path
import os
import pathlib
import shutil
import paramiko
import pandas as pd
import select

def get_cmd_all_drivers_modinfo():
    return '/usr/sbin/modinfo $(find /lib/modules/ -regex ".*\.\(ko\|ko.xz\)$")'


def get_cmd_all_running_drivers_modinfo():
    return '/usr/sbin/modinfo $(cat /proc/modules | awk \'{print $1}\')'


def async_run_cmd(cmd, line_handler, line_handler_arg, start, condition, sshClient=None):
    if sshClient is not None:
        stdin, stdout, stderr = sshClient.exec_command(cmd)
        channel = sshClient.get_transport().open_session()
        channel.exec_command(cmd)
            
        while not channel.exit_status_ready():
            r, w, x = select.select([channel], [], [])
            if len(r) > 0:
                recv = channel.recv(1024)
                recv = str(recv, 'utf-8').splitlines()
                for line in recv:
                    line_handler(line_handler_arg, line, start, condition)
                    start += 1

        channel.close()
        # del stdin, stdout, stderr
    else:
        cmd_runner = subprocess.Popen(cmd,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        for line in cmd_runner.stdout:
            line = str(line, 'utf-8')
            line_handler(line_handler_arg, line, start, condition)
            start += 1


def run_cmd(cmd, sshClient=None, timeout=None):
    if sshClient is not None:
        stdin, stdout, stderr = sshClient.exec_command(cmd, timeout=timeout)
        
        result = stdout.read()

        return result
    else:
        cmd_runner = subprocess.Popen(cmd,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        result, errs = cmd_runner.communicate()

        return result


class RPMReader:
    def __init__(self, logger):
        self.logger = logger
        self.columns = ['Name', 'Path', 'Vendor', 'Signature', 'Distribution', 'Driver Flag: supported']
    
    def get_support_flag_from_rpm(self, rpm: str) -> dict:
        Path('tmp').mkdir(parents=True, exist_ok=True)
        os.chdir('tmp')

        command = 'rpm2cpio %s | cpio -idmv' % rpm
        rpm_unpack = subprocess.Popen(command,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        rpm_unpack.wait()

        driver_supported = ""
        rpm_dir = pathlib.Path('.')
        drivers = tuple(rpm_dir.rglob('*.ko'))
        if len(drivers) < 1:
            os.chdir('../')
            shutil.rmtree('tmp')

            return driver_supported

        for driver in drivers:
            raw_info = run_cmd('/usr/sbin/modinfo %s' % driver)
            raw_info = str(raw_info, 'utf-8')
            info_list = raw_info.splitlines()
            found_supported = False
            for item in info_list:
                values = item.split(':')
                if len(values) < 2:
                    continue

                if values[0].rstrip() == 'supported':
                    found_supported = True
                    driver_supported += str(driver) + ": " + ":".join(values[1:]).lstrip() + "\n"
            if found_supported is False:
                driver_supported += str(driver) + ": Missing" + "\n"

        os.chdir('../')
        shutil.rmtree('tmp')

        return driver_supported

    def format_rpm_info(self, rpm_files, raw_output, row_handlers, query='all'):
        raw_output = str(raw_output, 'utf-8').split("Name        :")
        rpms = raw_output[1:]

        for i, rpm in enumerate(rpm_files):
            info = rpms[i].splitlines()
            name = info[0].lstrip()
            signature = ''
            distribution = ''
            vendor = ''
            for item in info:
                values = item.split(':')
                if len(values) < 2:
                    continue

                if values[0].rstrip() == "Signature":
                    signature = ":".join(values[1:])
                elif values[0].rstrip() == "Distribution":
                    distribution = ":".join(values[1:])
                elif values[0].rstrip() == "Vendor":
                    vendor = ":".join(values[1:])

            driver_supported = self.get_support_flag_from_rpm(rpm)

            if not self.query_filter(driver_supported, query):
                continue

            for handler in row_handlers:
                handler([name, rpm, vendor, signature, distribution, driver_supported])
    
    def query_filter(self, supported, query):
        if query == 'all':
            return True
        elif query == 'suse' and ': yes' in supported:
            return True
        elif query == 'vendor' and ': external' in supported:
            return True
        elif query == 'unknow' and ': Missing' in supported:
            return True
        
        return False

    def add_row(self, row):
        self.rpm_df = self.rpm_df.append(pd.Series(row, index=self.columns), ignore_index=True)

    def GetRPMsInfo(self, path, row_handlers=None, query="all"):
        rpm_files = run_cmd('find ' + path + ' -name "*.rpm"')
        rpm_files = str(rpm_files, 'utf-8').splitlines()
        rpm_infos = run_cmd('rpm -qpi --nosignature $(find ' + path + ' -name "*.rpm")')

        if row_handlers is None:
            row_handlers = []

        self.rpm_df = pd.DataFrame(columns=self.columns)
        row_handlers.append(self.add_row)
        self.format_rpm_info(rpm_files, rpm_infos, row_handlers, query)

        return self.rpm_df

    
    def GetRPMInfo(self, file):
        self.rpm_df = pd.DataFrame(columns=self.columns)
        rpm_infos = run_cmd('rpm -qpi --nosignature ' + file)

        self.format_rpm_info([file], rpm_infos, [self.add_row])

        return self.rpm_df

class DriverReader:
    def __init__(self, logger, progress):
        self.logger = logger
        self.progress = progress
        self.columns = ['Name', 'Path', 'Flag: supported', 'SUSE Release', 'Running', 'RPM Information']

    def connect(self, hostname, user, password, ssh_port):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(hostname=hostname,
                            username=user,
                            password=password,
                            port=ssh_port)
            return True
        except paramiko.ssh_exception.SSHException:
            self.logger.error("Can not connect to server: %s", hostname)
            return False

    def query_filter(self, supported, query='all'):
        if query == 'all':
            return True
        elif query == 'suse' and supported == 'yes':
            return True
        elif query == 'vendor' and supported == 'external':
            return True
        elif query == 'unknow' and (supported != 'yes' and supported != 'no'):
            return True

        return False

    def get_remote_drivers(self, ip='127.0.0.1', user='', password='', ssh_port=22, query='all'):
        if not self.connect(ip, user, password, ssh_port):
            return None

        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo(), self.ssh)
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo(), self.ssh)

        driver_table = self.fill_driver_info(ip, drivers_modinfo, running_drivers_modinfo, query, True)

        return driver_table

    def get_local_drivers(self, query='all', row_handlers=[]):
        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo())
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo())

        driver_table = self.fill_driver_info('local host', drivers_modinfo, running_drivers_modinfo, query)

        return driver_table
    
    def modinfo_to_list(self, raw_output):
        raw_output = str(raw_output, 'utf-8')
        raw_output = list(raw_output.split('filename:'))

        return raw_output[1:]

    def get_driver_files(self, running_driver_info):
        files = []
        for driver in running_driver_info:
            driver = driver.splitlines()
            files.append(driver[0].lstrip().rstrip())

        return files
    
    def fill_driver_rpm_info(self, driver_files, item_handler, rpm_table, query, remote):
        start = 0
        step = 1000
        finished = False
        total = len(driver_files)
        while not finished:
            if start+step >= total:
                end = total - 1
                finished = True
            else:
                end = start + step

            cmd = 'rpm -qf ' + ' '.join(driver_files[start: end])
            if remote:
                async_run_cmd(cmd, item_handler, rpm_table, start, query, self.ssh)
            else:
                async_run_cmd(cmd, item_handler, rpm_table, start, query)

            start = end + 1

    def add_row_handler(self, rpm_table, rpm_info, index, query):
        if rpm_info is '':
            return

        supported = rpm_table[index]['supported']
        self.progress.advance(self.task)
        if self.query_filter(supported, query):
            row = [rpm_table[index]['name'], rpm_table[index]['path'], supported, rpm_table[index]['suserelease'], rpm_table[index]['running'], rpm_info]
            self.driver_df = self.driver_df.append(pd.Series(row, index=self.columns), ignore_index=True)

            self.progress.console.print(f"Found driver: {rpm_table[index]['path']}")
        
    def fill_driver_info(self, ip, drivers_modinfo, running_drivers_modinfo, query='all', remote=False):
        drivers_modinfo = set(self.modinfo_to_list(drivers_modinfo))
        running_drivers_modinfo = set(self.modinfo_to_list(running_drivers_modinfo))

        drivers_modinfo = drivers_modinfo.union(running_drivers_modinfo)
        total_drivers = len(drivers_modinfo)
        self.task = self.progress.add_task(ip + "; total drivers: " + str(total_drivers), total=total_drivers)

        driver_files = self.get_driver_files(drivers_modinfo)
        running_driver_files = self.get_driver_files(running_drivers_modinfo)

        rpm_table = []
        for driver in drivers_modinfo:
            driver = driver.splitlines()
            filename = driver[0].lstrip().rstrip()
            name = ''
            supported = 'Missing'
            suserelease = 'Missing'
            running = str(filename in running_driver_files)
            
            driver = driver[1:]
            
            for item in driver:
                values = item.split(':')
                if len(values) < 2:
                    continue

                if values[0] == "supported":
                    supported = ":".join(values[1:]).lstrip()
                elif values[0] == "suserelease":
                    suserelease = ":".join(values[1:]).lstrip()
                elif values[0] == "name":
                    name = ":".join(values[1:]).lstrip()
            
            if name == '':
                name = Path(filename).name
            rpm_set = {"name": name, 
                    "path": filename, 
                    "supported": supported, 
                    "suserelease": suserelease, 
                    "running": running, 
                    "rpm_info": ""}

            rpm_table.append(rpm_set)
        
        self.driver_df = pd.DataFrame(columns=self.columns)
        self.fill_driver_rpm_info(driver_files, self.add_row_handler, rpm_table, query, remote)
    
        return self.driver_df
