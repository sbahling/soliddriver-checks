import subprocess
from pathlib import Path
import os
import paramiko
import pandas as pd
import select
import re
from collections import namedtuple
import tempfile
from paramiko.ssh_exception import NoValidConnectionsError, SSHException


def get_cmd_all_drivers_modinfo():
    return '/usr/sbin/modinfo $(find /lib/modules/ -regex ".*\.\(ko\|ko.xz\)$")'


def get_cmd_all_running_drivers_modinfo():
    return '/usr/sbin/modinfo $(cat /proc/modules | awk \'{print $1}\')'


def async_run_cmd(cmd, line_handler,
                  line_handler_arg, start, condition, sshClient=None):
    if sshClient is not None:
        channel = sshClient.get_transport().open_session()
        channel.exec_command(cmd)

        while not channel.exit_status_ready():
            r, __, __ = select.select([channel], [], [])
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
        __, stdout, __ = sshClient.exec_command(cmd, timeout=timeout)

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
    def __init__(self, progress):
        self._progress = progress
        self._columns = ['Name',
                         'Path',
                         'Vendor',
                         'Signature',
                         'Distribution',
                         'Driver Flag: supported',
                         'Symbols Check']

    def _driver_symbols_check(self, rpm_symbols, driver):
        symvers = run_cmd('/usr/sbin/modprobe --dump-modversions %s' % driver)

        result = dict()
        result['unfound'] = []
        result['checksum-mismatch'] = []
        for line in symvers.splitlines():
            line = str(line, 'utf-8')
            chksum, sym = line.split()
            chksum = hex(int(chksum, base=16))

            req = rpm_symbols.get(sym, None)
            if req is None:
                result['unfound'].append(sym)
                # result.append('Symbol %s not found in rpm requires' % sym)
                continue

            if req.checksum != chksum:
                result['checksum-mismatch'].append('rpm checksum: %s, driver checksum: %s' % (chksum, req.checksum))
                # result.append('Symbol checksum does not match, module depends on %s, rpm requires %s' % (chksum, req.checksum))
                continue

        return result

    def _get_rpm_symbols(self, rpm):
        KernelSym = namedtuple('KernelSym', 'kernel_flavor symbol checksum')
        symver_re = re.compile(r'ksym\((.*):(.*)\) = (.+)')
        raw_symbols = run_cmd('rpm -q --requires %s' % rpm)

        mod_reqs = {}
        for line in raw_symbols.splitlines():
            line = str(line, 'utf-8')
            result = symver_re.match(line)
            if result:
                flavor, sym, chksum = result.groups()
                chksum = hex(int(chksum, base=16))
                mod_reqs[sym] = KernelSym(kernel_flavor=flavor,
                                          symbol=sym, checksum=chksum)

        return mod_reqs

    def _get_driver_supported(self, driver):
        raw_info = run_cmd('/usr/sbin/modinfo %s' % driver)
        raw_info = str(raw_info, 'utf-8')
        info_list = raw_info.splitlines()
        for item in info_list:
            values = item.split(':')
            if len(values) < 2:
                continue

            if values[0].strip() == 'supported':
                return ":".join(values[1:]).strip()

        return "Missing"

    def _fmt_driver_supported(self, drivers):
        supported = dict()
        for d in drivers:
            supported[d] = drivers[d]['supported']

        return supported

    def _fmt_driver_symbol(self, drivers):
        symbols = dict()
        for d in drivers:
            d_info = dict()
            d_info['unfound'] = drivers[d]['symbols']['unfound']
            d_info['checksum-mismatch'] = drivers[d]['symbols']['checksum-mismatch']
            if len(d_info['unfound']) == 0 and len(d_info['checksum-mismatch']) == 0:
                continue
            else:
                symbols[d] = d_info

        return symbols

    def _driver_checks(self, rpm: str):
        mod_reqs = self._get_rpm_symbols(rpm)

        tmp = tempfile.TemporaryDirectory()

        command = 'rpm2cpio %s | cpio -idmv -D %s' % (rpm, tmp.name)
        run_cmd(command)

        rpm_dir = Path(tmp.name)
        files = tuple(rpm_dir.rglob('*.*'))
        drivers = [i for i in files if re.search(r'\.(ko|ko\.xz)$', str(i))]
        result = dict()

        if len(drivers) < 1:
            tmp.cleanup()

            return None

        for driver in drivers:
            item = dict()
            item['symbols'] = self._driver_symbols_check(mod_reqs, driver)
            item['supported'] = self._get_driver_supported(driver)

            dpath = str(driver)
            dpath = dpath[dpath.startswith(tmp.name) + len(tmp.name) - 1:]
            result[dpath] = item

        tmp.cleanup()

        return result

    def _format_rpm_info(self, rpm_files,
                         raw_output, row_handlers, query='all'):
        raw_output = str(raw_output, 'utf-8').split("Name        :")
        rpms = raw_output[1:]

        for i, rpm in enumerate(rpm_files):
            info = rpms[i].splitlines()
            name = info[0].strip()
            signature = ''
            distribution = ''
            vendor = ''
            for item in info:
                values = item.split(':')
                if len(values) < 2:
                    continue

                if values[0].strip() == "Signature":
                    signature = ":".join(values[1:])
                elif values[0].strip() == "Distribution":
                    distribution = ":".join(values[1:])
                elif values[0].strip() == "Vendor":
                    vendor = ":".join(values[1:])

            driver_checks = self._driver_checks(rpm)

            supported = ""
            symbols = ""
            if driver_checks is not None:
                supported = self._fmt_driver_supported(driver_checks)
                symbols = self._fmt_driver_symbol(driver_checks)

            if not self._query_filter(supported, query):
                continue

            for handler in row_handlers:
                handler([name, rpm, vendor, signature,
                         distribution, supported, symbols])

            self._progress.console.print('[bright_black]*********************************************************************[/]')
            self._progress.console.print('name           : %s' % name)
            self._progress.console.print('path           : %s' % rpm)
            self._progress.console.print('vendor         : %s' % vendor)
            self._progress.console.print('signature      : %s' % signature)
            self._progress.console.print('disturibution  : %s' % distribution)
            if 'Missing' in supported or 'yes' in supported:
                self._progress.console.print('[bold red]supported flag : failed \n%s[/]' % supported)
            else:
                self._progress.console.print('supported flag : success')
            if '.ko' in symbols:
                self._progress.console.print('[bold red]symbols checks : failed \n%s[/]' % symbols)
            else:
                self._progress.console.print('symbols checks : success')

            self._progress.advance(self._task)

    def _query_filter(self, supported, query):
        if query == 'all':
            return True
        elif query == 'suse' and ': yes' in supported:
            return True
        elif query == 'vendor' and ': external' in supported:
            return True
        elif query == 'unknow' and ': Missing' in supported:
            return True

        return False

    def _add_row(self, row):
        self._rpm_df = self._rpm_df.append(pd.Series(row, index=self._columns),
                                           ignore_index=True)

    def get_rpms_info(self, path, row_handlers=None, query="all"):
        cmd_rpms = 'find %s -regextype sed -regex \'.*-kmp-.*\.rpm$\'' % path
        rpm_files = run_cmd(cmd_rpms)
        rpm_files = str(rpm_files, 'utf-8').splitlines()

        self._task = self._progress.add_task("[italic][bold][green] Checking RPMs "
                                             + "; Total RPMs: "
                                             + str(len(rpm_files)),
                                             total=len(rpm_files))

        rpm_infos = run_cmd('rpm -qpi --nosignature $(%s)' % cmd_rpms)

        if row_handlers is None:
            row_handlers = []

        self._rpm_df = pd.DataFrame(columns=self._columns)
        row_handlers.append(self._add_row)
        self._format_rpm_info(rpm_files, rpm_infos, row_handlers, query)

        return self._rpm_df

    def get_rpm_info(self, rpmfile):
        self._rpm_df = pd.DataFrame(columns=self._columns)
        rpm_infos = run_cmd('rpm -qpi --nosignature %s' % rpmfile)

        self._format_rpm_info([rpmfile.name], rpm_infos, [self._add_row])

        return self._rpm_df


class DriverReader:
    def __init__(self, progress):
        self._progress = progress
        self._columns = ['Name',
                         'Path',
                         'Flag: supported',
                         'SUSE Release',
                         'Running',
                         'RPM Information']
        self._ssh = None

    def _connect(self, hostname, user, password, ssh_port):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._ssh.connect(hostname=hostname,
                              username=user,
                              password=password,
                              port=ssh_port)
            return True
        except NoValidConnectionsError as e:
            self._progress.console.print(f"[bold red]Can not connect to {hostname}, failed: {e}[/]")
        except SSHException as e:
            self._progress.console.print(f"[bold red]Can not connect to {hostname}, failed: {e}[/]")

        return False

    def _query_filter(self, supported, query='all'):
        if query == 'all':
            return True
        elif query == 'suse' and supported == 'yes':
            return True
        elif query == 'vendor' and supported == 'external':
            return True
        elif query == 'unknow' and (supported != 'yes' and supported != 'no'):
            return True

        return False

    def get_remote_drivers(self, ip='127.0.0.1', user='', password='',
                           ssh_port=22, query='all'):
        if not self._connect(ip, user, password, ssh_port):
            return None

        try:
            drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo(), self._ssh)
            running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo(), self._ssh)

            driver_table = self._fill_driver_info(ip, drivers_modinfo,
                                                  running_drivers_modinfo,
                                                  query, True)
        except NoValidConnectionsError as e:
            self._progress.console.print(f"[bold red]Connect to {ip} failed : {e}[/]")
        finally:
            pass

        self._progress.update(self._task, visible=False)

        return driver_table

    def get_local_drivers(self, query='all', row_handlers=[]):
        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo())
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo())

        driver_table = self._fill_driver_info('local host',
                                              drivers_modinfo,
                                              running_drivers_modinfo, query)

        return driver_table

    def _modinfo_to_list(self, raw_output):
        raw_output = str(raw_output, 'utf-8')
        raw_output = list(raw_output.split('filename:'))

        return raw_output[1:]

    def _get_driver_files(self, running_driver_info):
        files = []
        for driver in running_driver_info:
            driver = driver.splitlines()
            files.append(driver[0].strip())

        return files
    
    def _fill_driver_rpm_info(self, driver_files,
                              item_handler, rpm_table, query, remote):
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
                async_run_cmd(cmd, item_handler,
                              rpm_table, start, query, self._ssh)
            else:
                async_run_cmd(cmd, item_handler, rpm_table, start, query)

            start = end + 1

    def _add_row_handler(self, rpm_table, rpm_info, index, query):
        if rpm_info == '':
            return

        supported = rpm_table[index]['supported']
        self._progress.advance(self._task)
        if self._query_filter(supported, query):
            row = [rpm_table[index]['name'],
                   rpm_table[index]['path'],
                   supported,
                   rpm_table[index]['suserelease'],
                   rpm_table[index]['running'], rpm_info]
            self._driver_df = self._driver_df.append(pd.Series(row, index=self._columns), ignore_index=True)

            if self._ssh is None:
                self._progress.console.print(f"[light_steel_blue]Found driver: {rpm_table[index]['path']}[/light_steel_blue]")

    def _fill_driver_info(self, ip, drivers_modinfo,
                          running_drivers_modinfo, query='all', remote=False):
        drivers_modinfo = set(self._modinfo_to_list(drivers_modinfo))
        running_drivers_modinfo = set(self._modinfo_to_list(running_drivers_modinfo))

        drivers_modinfo = drivers_modinfo.union(running_drivers_modinfo)
        total_drivers = len(drivers_modinfo)
        self._task = self._progress.add_task("[italic][bold][green] Working on: "
                                             + ip
                                             + "; Total Drivers: "
                                             + str(total_drivers),
                                             total=total_drivers)

        driver_files = self._get_driver_files(drivers_modinfo)
        running_driver_files = self._get_driver_files(running_drivers_modinfo)

        rpm_table = []
        for driver in drivers_modinfo:
            driver = driver.splitlines()
            filename = driver[0].strip()
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
                    supported = ":".join(values[1:]).strip()
                elif values[0] == "suserelease":
                    suserelease = ":".join(values[1:]).strip()
                elif values[0] == "name":
                    name = ":".join(values[1:]).strip()

            if name == '':
                name = Path(filename).name
            rpm_set = {"name": name,
                       "path": filename,
                       "supported": supported,
                       "suserelease": suserelease,
                       "running": running,
                       "rpm_info": ""}

            rpm_table.append(rpm_set)

        self._driver_df = pd.DataFrame(columns=self._columns)
        self._fill_driver_rpm_info(driver_files, self._add_row_handler,
                                   rpm_table, query, remote)

        return self._driver_df
