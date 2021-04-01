import subprocess
from pathlib import Path
import os
import paramiko
import pandas as pd
import select
import re
from collections import namedtuple
import tempfile


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
    def __init__(self, logger):
        self._logger = logger
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

            if values[0].rstrip() == 'supported':
                return ":".join(values[1:]).lstrip()

        return "Missing"

    def _drivers_terminal_format(self, drivers):
        supported = ""
        symbols = ""
        for driver in drivers:
            supported += "%s : %s\n" % (driver, drivers[driver]['supported'])
            syms = drivers[driver]['symbols']

            if len(syms['unfound']) == 0 and len(syms['checksum-mismatch']) == 0:
                continue
            else:
                symbols += "********************\nSymbols error founded in driver: %s\n" % driver

            if len(syms['unfound']) > 0:
                symbols += "Symbols not found in rpm requires:\n %s\n" % syms['unfound']

            if len(syms['checksum-mismatch']) > 0:
                symbols += "Symbol checksum does not match:\n %s\n" % syms['checksum-mismatch']

        return supported, symbols

    def _driver_checks(self, rpm: str):
        mod_reqs = self._get_rpm_symbols(rpm)

        tmp = tempfile.TemporaryDirectory()
        # Path('tmp').mkdir(parents=True, exist_ok=True)

        command = 'rpm2cpio %s | cpio -idmv -D %s' % (rpm, tmp.name)
        rpm_unpack = subprocess.Popen(command,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        rpm_unpack.wait()

        rpm_dir = Path(tmp.name)
        files = tuple(rpm_dir.rglob('*.*'))
        drivers = [i for i in files if re.search(r'\.(ko|xz\.ko)$', str(i))]
        result = dict()

        if len(drivers) < 1:
            # os.chdir('../')
            # shutil.rmtree('tmp')
            tmp.cleanup()

            return None

        for driver in drivers:
            item = dict()
            item['symbols'] = self._driver_symbols_check(mod_reqs, driver)
            item['supported'] = self._get_driver_supported(driver)

            dpath = str(driver)
            dpath = dpath[dpath.startswith(tmp.name) + len(tmp.name) - 1:]
            result[dpath] = item

        # os.chdir('../')
        # shutil.rmtree('tmp')
        tmp.cleanup()

        return result

    def _format_rpm_info(self, rpm_files,
                         raw_output, row_handlers, query='all'):
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

            driver_checks = self._driver_checks(rpm)

            supported = ""
            symbols = ""
            if driver_checks is not None:
                supported, symbols = self._drivers_terminal_format(driver_checks)

            if not self._query_filter(supported, query):
                continue

            for handler in row_handlers:
                handler([name, rpm, vendor, signature,
                         distribution, supported, symbols])

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
        rpm_files = run_cmd('find %s -name "*.rpm"' % path)
        rpm_files = str(rpm_files, 'utf-8').splitlines()
        rpm_infos = run_cmd('rpm -qpi --nosignature $(find %s -name "*.rpm")' % path)

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
    def __init__(self, logger, progress):
        self._logger = logger
        self._progress = progress
        self._columns = ['Name',
                         'Path',
                         'Flag: supported',
                         'SUSE Release',
                         'Running',
                         'RPM Information']

    def _connect(self, hostname, user, password, ssh_port):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._ssh.connect(hostname=hostname,
                              username=user,
                              password=password,
                              port=ssh_port)
            return True
        except paramiko.ssh_exception.SSHException:
            self._logger.error("Can not connect to server: %s", hostname)
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

        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo(), self._ssh)
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo(), self._ssh)

        driver_table = self._fill_driver_info(ip, drivers_modinfo,
                                              running_drivers_modinfo,
                                              query, True)

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
            files.append(driver[0].lstrip().rstrip())

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

        self._driver_df = pd.DataFrame(columns=self._columns)
        self._fill_driver_rpm_info(driver_files, self._add_row_handler,
                                   rpm_table, query, remote)

        return self._driver_df
