import subprocess
import shlex
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

def async_run_cmd(cmd, line_handler, line_handler_arg, sshClient=None):
    if sshClient is not None:
        stdin, stdout, stderr = sshClient.exec_command(cmd)
        channel = sshClient.get_transport().open_session()
        channel.exec_command(cmd)

        while True:
            if channel.exit_status_ready():
                break

            r, w, x = select.select([channel], [], [])
            if len(r) > 0:
                recv = channel.recv(1024)
                recv = str(recv, 'utf-8').splitlines()
                for line in recv:
                    line_handler(line_handler_arg, line)

        channel.close()
        del stdin, stdout, stderr
    else:
        cmd_runner = subprocess.Popen(cmd,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        for line in cmd_runner.stdout:
            line = str(line, 'utf-8')
            line_handler(line_handler_arg, line)


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


    def format_rpm_info(self, rpm_files, raw_output, row_handlers):
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

            for handler in row_handlers:
                handler(name, rpm, vendor, signature, distribution, driver_supported)

    def get_suse_support_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains(': yes')]
        return df

    def get_vendor_support_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains(': external')]
        return df

    def get_unknow_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains(': Missing')]
        return df

    def GetRPMsInfo(self, path, row_handlers=None, query="all"):
        rpm_files = run_cmd('find ' + path + ' -name "*.rpm"')
        rpm_files = str(rpm_files, 'utf-8').splitlines()
        rpm_infos = run_cmd('rpm -qpi --nosignature $(find ' + path + ' -name "*.rpm")')

        rpm_table = self.TableFormatter(self.logger)

        if row_handlers is None:
            row_handlers = []

        row_handlers.append(rpm_table.add_row)
        self.format_rpm_info(rpm_files, rpm_infos, row_handlers)

        rpms = rpm_table.get_table()

        if query == 'all':
            return rpms
        elif query == 'suse':
            return self.get_suse_support_rpms(rpms)
        elif query == 'vendor':
            return self.get_vendor_support_rpms(rpms)
        elif query == 'unknow':
            return self.get_unknow_rpms(rpms)

        return rpms

    
    def GetRPMInfo(self, file):
        rpm_infos = run_cmd('rpm -qpi --nosignature ' + file)
        rpm_table = self.TableFormatter(self.logger)
        self.format_rpm_info([file], rpm_infos, rpm_table.add_row)

        return rpm_table.get_table()

    class TableFormatter:
        def __init__(self, logger):
            self.logger = logger
            self.driver_df = pd.DataFrame({'Name': [],
                                  'Path': [],
                                  'Vendor': [],
                                  'Signature': [],
                                  'Distribution': [],
                                  'Driver Flag: supported': []})

        def add_row(self, name, path, vendor, signature, distribution, driver_supported):
            new_row = {'Name': name,
                'Path': path,
                'Vendor': vendor,
                'Signature': signature,
                'Distribution': distribution,
                'Driver Flag: supported': driver_supported}
            
            # self.logger.info("name: %s, path: %s, vendor: %s, signature: %s, distribution: %s, driver_supported: %s", 
            #                 name, path, vendor, signature, distribution, driver_supported)

            self.driver_df = self.driver_df.append(new_row, ignore_index=True)
        
        def get_table(self, filter='all'):
            return self.driver_df

class DriverReader:
    def __init__(self, logger):
        self.logger = logger

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
    
    def get_suse_support_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Flag: Supported']] == 'yes'
        return rslt_df

    def get_vendor_support_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Flag: Supported']] == 'external'
        return rslt_df

    def get_unknow_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Flag: Supported']] == 'Missing'
        return rslt_df

    def get_query_drivers(self, drivers, query='all'):
        if query == 'all':
            return driver_table
        elif query == 'suse':
            return self.get_suse_support_drivers(driver_table)
        elif query == 'vendor':
            return self.get_vendor_support_drivers(driver_table)
        elif query == 'unknow':
            return self.get_unknow_drivers(driver_table)

    def get_remote_drivers(self, ip='127.0.0.1', user='', password='', ssh_port=22, query='all'):
        if not self.connect(ip, user, password, ssh_port):
            return None

        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo(), self.ssh)
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo(), self.ssh)

        driver_table = self.fill_driver_info(drivers_modinfo, running_drivers_modinfo, True)

        return get_query_drivers(driver_table)

    def get_local_drivers(self, query='all'):
        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo())
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo())

        driver_table = self.fill_driver_info(drivers_modinfo, running_drivers_modinfo)

        return get_query_drivers(driver_table)
    
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
    
    def fill_driver_rpm_info(self, driver_files, item_handler, item_handler_arg, remote):
        start = 0
        step = 1000
        finished = False
        while not finished:
            if start+step > len(driver_files):
                end = len(driver_files) - start - 1
                finished = True
            else:
                end = start + step
            cmd = 'rpm -qf ' + ' '.join(driver_files[start: end])
            if remote:
                async_run_cmd(cmd, item_handler, item_handler_arg, self.ssh)
            else:
                async_run_cmd(cmd, item_handler, item_handler_arg)

            start = end + 1

    def fill_driver_info(self, drivers_modinfo, running_drivers_modinfo, remote=False):
        drivers_modinfo = set(self.modinfo_to_list(drivers_modinfo))
        running_drivers_modinfo = set(self.modinfo_to_list(running_drivers_modinfo))

        drivers_modinfo = drivers_modinfo.union(running_drivers_modinfo)

        driver_files = self.get_driver_files(drivers_modinfo)
        running_driver_files = self.get_driver_files(running_drivers_modinfo)

        rpm_table = []
        for i, driver in enumerate(drivers_modinfo):
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
            
            if name is '':
                name = Path(filename).name
            rpm_set = {"name": name, 
                    "path": filename, 
                    "supported": supported, 
                    "suserelease": suserelease, 
                    "running": running, 
                    "rpm_info": ""}

            rpm_table.append(rpm_set)
        
        full_table = self.TableFormatter(self.logger)
        self.fill_driver_rpm_info(driver_files, full_table.add_row_handler, rpm_table, remote)
    
        return full_table.get_table()
    
    class TableFormatter:
        def __init__(self, logger):
            self.driver_df = pd.DataFrame({'Name': [],
                                'Path': [],
                                'Flag: supported': [],
                                'SUSE Release': [],
                                'Running': [],
                                'RPM Information': []})
            self.logger = logger
    
        def add_row_handler(self, rpm_table, rpm_info):
            if rpm_info is '':
                return

            index = len(self.driver_df.index)
            new_row = {'Name': rpm_table[index]['name'],
               'Path': rpm_table[index]['path'],
               'Flag: supported': rpm_table[index]['supported'],
               'SUSE Release': rpm_table[index]['suserelease'],
               'Running': rpm_table[index]['running'],
                'RPM Information': rpm_info}

            # self.logger.info("name: %s, path: %s, supported: %s, suserelease: %s, running: %s, rpm information: %s", 
            #             rpm_table[index]['name'],rpm_table[index]['path'],rpm_table[index]['supported'],rpm_table[index]['suserelease'], 
            #             rpm_table[index]['running'], rpm_info)
            self.driver_df = self.driver_df.append(new_row, ignore_index=True)
            
        def add_row(self, name, path, supported, suserelease, running, rpm_info):
            new_row = {'Name': name,
                'Path': path,
                'Flag: supported': supported,
                'SUSE Release': suserelease,
                'Running': running,
                'RPM Information': rpm_info}

            self.logger.info("name: %s, path: %s, supported: %s, suserelease: %s, running: %s, rpm information: %s", 
                            name, path, supported, suserelease, running, rpm_info)

            self.driver_df = self.driver_df.append(new_row, ignore_index=True)
        
        def get_table(self, filter='all'):
            return self.driver_df
