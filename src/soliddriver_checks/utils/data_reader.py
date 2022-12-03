import subprocess
from pathlib import Path
import os
import paramiko
import pandas as pd
# import select
import re
from collections import namedtuple
import tempfile
import fnmatch
import json
from scp import SCPClient
from paramiko.ssh_exception import NoValidConnectionsError, SSHException


def get_cmd_all_drivers_modinfo():
    return '/usr/sbin/modinfo $(find /lib/modules/ -regex ".*\.\(ko\|ko.xz\|ko.zst\)$") 2>&1'


def get_cmd_all_running_drivers_modinfo():
    return "/usr/sbin/modinfo $(cat /proc/modules | awk '{print $1}') 2>&1"


def async_run_cmd(
    cmd, line_handler, line_handler_arg, start, end, condition, sshClient=None
):
    if sshClient is not None:
        __, stdout, __ = sshClient.exec_command(cmd)

        lines = stdout.read().decode().splitlines()
        for line in lines:
            line_handler(line_handler_arg, line.strip(), start, condition)
            start += 1
            if start >= end:
                break

        # channel = sshClient.get_transport().open_session()
        # channel.exec_command(cmd)

        # while not channel.exit_status_ready():
        #     r, __, __ = select.select([channel], [], [])
        #     if len(r) > 0:
        #         recv = channel.recv(1024)
        #         recv = str(recv, "utf-8").splitlines()
        #         for line in recv:
        #             line_handler(line_handler_arg, line, start, condition)
        #             start += 1

        # channel.close()
    else:
        cmd_runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for line in cmd_runner.stdout:
            line = str(line, "utf-8")
            line_handler(line_handler_arg, line, start, condition)
            start += 1
            if start >= end:
                break


def run_cmd(cmd, sshClient=None, timeout=None):
    if sshClient is not None:
        __, stdout, __ = sshClient.exec_command(cmd, timeout=timeout)
        result = stdout.read()
        return str(result, "utf-8")
    else:
        cmd_runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        result, __ = cmd_runner.communicate()
        return str(result, "utf-8")

        
class KMPReader:
    def get_all_kmp_files(self, path):
        cmd = "find %s -regextype sed -regex '.*-kmp-.*\.rpm$'" % path
        kmps = run_cmd(cmd)
        
        return kmps.splitlines()

    def collect_kmp_data(self, path):
        base_info = self._get_kmp_info(path)
        wm2_invoked = self._check_kmp_wm2_invoked(path)
        reqs = self._get_kmp_requires(path)
        modalias = self._get_kmp_modalias(path)
        km_info = self._get_km_all_info(path)

        return {"name"         : base_info.get("Name"),
                "path"         : path,
                "vendor"       : base_info.get("Vendor"),
                "signature"    : base_info.get("Signature"),
                "license"      : base_info.get("License"),
                "wm2_invoked"  : wm2_invoked,
                "reqs"         : reqs,
                "modalias"     : modalias,
                "km_info"      : km_info}

    def _get_km_symbols(self, path):
        cmd = "/usr/sbin/modprobe --dump-modversions %s" % path
        symbols = run_cmd(cmd)

        lines = symbols.splitlines()
        symver = {}
        for line in lines:
            kv = line.split()
            symver[kv[1]] = kv[0]

        return symver

    def _get_km_supported_flag(self, path):
        cmd = "/usr/sbin/modinfo --field=supported %s" % path
        values = run_cmd(cmd)

        return values.splitlines()

    def _get_km_license(self, path):
        cmd = "/usr/sbin/modinfo --field=license %s" % path
        license = run_cmd(cmd)
        
        return license.splitlines()
    
    def _get_km_signature(self, path):
        cmd = "/usr/sbin/modinfo --field=signature %s" % path
        signature = run_cmd(cmd)
        
        return signature
    
    def _get_km_alias(self, path):
        alias = run_cmd("/usr/sbin/modinfo --field=alias %s | grep pci:" % path)
        return alias.splitlines()
    
    def _get_km_all_info(self, rpm_path):
        tmp = tempfile.TemporaryDirectory()

        command = "rpm2cpio %s | cpio -idmv -D %s" % (rpm_path, tmp.name)
        run_cmd(command)

        rpm_dir = Path(tmp.name)
        files = tuple(rpm_dir.rglob("*.*"))
        kms = [i for i in files if re.search(r"\.(ko|ko\.xz)$", str(i))]
        result = dict()

        if len(kms) < 1:
            tmp.cleanup()
            return result

        for km in kms:
            item = dict()
            item["symbols"] = self._get_km_symbols(km)
            item["supported"] = self._get_km_supported_flag(km)
            item["license"] = self._get_km_license(km)
            item["signature"] = self._get_km_signature(km)
            item["alias"] = self._get_km_alias(km)

            dpath = str(km)
            dpath = dpath[dpath.startswith(tmp.name) + len(tmp.name) - 1 :]
            result[dpath] = item

        tmp.cleanup()

        return result
        
    def _check_kmp_manifest(self, cmd_output):
        lines = cmd_output.splitlines()
        
        if len(lines) < 1: # no output also means good.
            return True, []

        items = lines[0].split(":")
        if len(items) < 3:  # example: error: ./tmp/a.rpm: not an rpm package (or package manifest)
            return True, []
        
        if items[0].strip() == "error":
             return False, items

        return True, []

    def _get_kmp_modalias(self, path):
        cmd = "".join("rpm -q --nosignature --supplements %s" % path)
        supplements = run_cmd(cmd)

        success, err_info = self._check_kmp_manifest(supplements)
        if not success:
            print(err_info)
            return []
        
        modalias = namedtuple("modalias", "kernel_flavor pci_re")
        ml_pci_re = re.compile(r"modalias\((.*):(.*\:.*)\)") # example: modalias(kernel-default:pci:v000019A2d00000712sv*sd*bc*sc*i*)
        ml_all_re = re.compile(r"modalias\((.*):(.*)\)")     # example: packageand(kernel-default:primergy-be2iscsi)
        
        alias_re = []
        for line in supplements.splitlines():
            pci_rst = ml_pci_re.match(line)
            all_rst = ml_all_re.match(line)
            if pci_rst:
                __, pci = pci_rst.groups()
                if "pci:" in pci: # only check PCI devices
                    alias_re.append(pci)
            elif all_rst: # match all (*) should not be allowed
                __, rst = all_rst.groups()
                if rst == "*":
                    alias_re.append(rst)

        return alias_re

    def _check_kmp_wm2_invoked(self, path):
        cmd = "".join("rpm -q --nosignature --scripts %s" % path)
        scripts = run_cmd(cmd)

        success, err_info = self._check_kmp_manifest(scripts)
        if not success:
            print(err_info)
            return False

        lines = scripts.splitlines()
        for line in lines:
            if "/usr/lib/module-init-tools/weak-modules2" in line:
                return True

        return False

    def _get_kmp_requires(self, path):
        cmd = "".join("rpm -q --nosignature --requires %s" % path)
        requires = run_cmd(cmd)

        KernelSym = namedtuple("KernelSym", "kernel_flavor symbol checksum")
        symver_re = re.compile(r"ksym\((.*):(.*)\) = (.+)")

        success, err_info = self._check_kmp_manifest(requires)
        if not success:
            print(err_info)
            return {}

        mod_reqs = {}
        for line in requires.splitlines():
            result = symver_re.match(line)
            if result:
                flavor, sym, chksum = result.groups()
                chksum = hex(int(chksum, base=16))
                mod_reqs[sym] = KernelSym(
                    kernel_flavor=flavor, symbol=sym, checksum=chksum
                )

        return mod_reqs
    
    def _get_kmp_info(self, path):
        cmd = "".join("rpm -q --nosignature --info %s" % path)
        info = run_cmd(cmd)
        
        success, err_info = self._check_kmp_manifest(info)
        if not success:
            print(err_info)
            return {}
        
        mod_info = {}
        lines = info.splitlines()
        for line in lines:
            kv = line.split(":")
            if len(kv) >= 2:
                mod_info[kv[0].strip()] = ":".join(kv[1:]).strip()
        
        return mod_info


class DriverReader:
    def __init__(self, progress):
        self._progress = progress
        self._columns = [
            "name",
            "path",
            "flag_supported",
            "license",
            "signature",
            "os-release",
            "running",
            "rpm",
            "rpm_sig_key",
        ]
        self._ssh = None

    def _connect(self, hostname, user, password, ssh_port):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._ssh.connect(
                hostname=hostname,
                username=user,
                password=password,
                port=ssh_port,
                allow_agent=False,
                look_for_keys=False,
            )
            return True
        except NoValidConnectionsError as e:
            self._progress.console.print(
                f"[bold red]Can not connect to {hostname}, failed: {e}[/]"
            )
        except SSHException as e:
            self._progress.console.print(
                f"[bold red]Can not connect to {hostname}, failed: {e}[/]"
            )

        return False

    def _run_script(self, script_file, remote=False):
        result = ""
        if remote:
            dist_path = "/tmp/check-links.sh"
            with SCPClient(self._ssh.get_transport()) as scp:
                scp.put(script_file, dist_path)
            result = run_cmd(dist_path, self._ssh).decode()
        else:
            result = run_cmd(script_file)

        return result

    # def _srcversion_checks(self, remote=False):
    #     pkg_path = os.path.dirname(__file__)
    #     script = f"{pkg_path}/scripts/srcversion-check.sh"
    #     result = self._run_script(script, remote)

    #     jstr = json.loads(result)
    #     df = pd.json_normalize(jstr["srcversions"])

    #     return df

    def _weak_update_driver_checks(self, remote=False):
        pkg_path = os.path.dirname(__file__)
        script = f"{pkg_path}/scripts/check-links.sh"
        result = self._run_script(script, remote)

        jstr = json.loads(result)
        df = pd.json_normalize(jstr["weak-drivers"])

        return df

    def _query_filter(self, supported, query="all"):
        if query == "all":
            return True
        elif query == "suse" and len(supported) == 1 and supported[0] == "yes":
            return True
        elif query == "vendor" and len(supported) == 1 and supported[0] == "external":
            return True
        elif query == "unknow" and (len(supported) == 0 or len(supported) > 1):
            return True

        return False

    def _find_noinfo_drivers(self, running_drivers):
        infos = str(running_drivers, "utf-8")
        d_names = []
        for line in infos.splitlines():
            if line.startswith("modinfo: ERROR: "):
                d_names.append(line.split(" ")[3])

        return d_names

    def get_remote_drivers(
        self, ip="127.0.0.1", user="", password="", ssh_port=22, query="all"
    ):
        if not self._connect(ip, user, password, ssh_port):
            return None

        try:
            drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo(), self._ssh)
            running_drivers_modinfo = run_cmd(
                get_cmd_all_running_drivers_modinfo(), self._ssh
            )

            noinfo_drivers = self._find_noinfo_drivers(running_drivers_modinfo)
            driver_table = self._fill_driver_info(
                ip, drivers_modinfo, running_drivers_modinfo, query, True
            )

            wu_driver_table = self._weak_update_driver_checks(remote=True)
            # srcv_t = self._srcversion_checks(remote=True)
        except NoValidConnectionsError as e:
            self._progress.console.print(f"[bold red]Connect to {ip} failed : {e}[/]")
        finally:
            pass

        self._progress.update(self._task, visible=False)

        return driver_table, wu_driver_table, noinfo_drivers

    def get_local_drivers(self, query="all", row_handlers=[]):
        drivers_modinfo = run_cmd(get_cmd_all_drivers_modinfo())
        running_drivers_modinfo = run_cmd(get_cmd_all_running_drivers_modinfo())

        driver_table = self._fill_driver_info(
            "local host", drivers_modinfo, running_drivers_modinfo, query
        )
        noinfo_drivers = self._find_noinfo_drivers(running_drivers_modinfo)

        wu_driver_table = self._weak_update_driver_checks()
        # srcv_t = self._srcversion_checks()

        return driver_table, wu_driver_table, noinfo_drivers

    def _modinfo_to_list(self, raw_output):
        raw_output = str(raw_output, "utf-8")
        raw_output = list(raw_output.split("filename:"))

        return raw_output[1:]

    def _get_rpm_sig_key(self, df_drivers, remote):
        df = df_drivers.copy()
        rpms = df.rpm.unique()

        rpms = [r for r in rpms if "not owned by any package" not in r and "" != r and "is not installed" not in r]

        sig_keys = dict()

        if len(rpms) < 1:
            return sig_keys

        rpmInfo = ""
        if remote:
            rpmInfo = run_cmd("rpm -qi %s" % (" ".join(rpms)), self._ssh)
        else:
            rpmInfo = run_cmd("rpm -qi %s" % (" ".join(rpms)))

        rpmInfo = rpmInfo.split("Name        :")
        rpmInfo = rpmInfo[1:]  # Skip "Name      :"
        for i, rpm in enumerate(rpms):
            info = rpmInfo[i].splitlines()
            key = ""
            for item in info:
                values = item.split(":")
                if len(values) < 2:
                    continue

                if values[0].strip() == "Signature":
                    key = ":".join(values[1:]).strip()
                    idx = key.find("Key ID")
                    if idx != -1:
                        key = key[idx + 7 :].strip()
            sig_keys[rpm] = key # give an empty value if there's no signature is found.

        return sig_keys

    def _fill_driver_rpm_info(self, d_files, item_handler, rpm_table, query, remote):
        start = 0
        # step = 1000
        step = 1
        finished = False
        total = len(d_files)
        while not finished:
            end = start + step
            if end > total:
                end = total
                finished = True

            cmd = "rpm -qf " + " ".join(d_files[start:end])
            if remote:
                async_run_cmd(
                    cmd, item_handler, rpm_table, start, end, query, self._ssh
                )
            else:
                async_run_cmd(cmd, item_handler, rpm_table, start, end, query)

            start = end

        rpm_sig_keys = self._get_rpm_sig_key(self._driver_df, remote)

        for i, row in self._driver_df.iterrows():
            if "not owned by any package" not in row["rpm"]:
                row["rpm_sig_key"] = rpm_sig_keys[row["rpm"]]
            elif "/weak-updates/" in row["path"]:
                row["rpm"] = "N/A"

    def _add_row_handler(self, rpm_table, rpm, index, query):
        if rpm == "":
            return

        supported = rpm_table[index]["flag_supported"]
        self._progress.advance(self._task)
        if self._query_filter(supported, query):
            # row = [
            #     rpm_table[index]["name"],
            #     rpm_table[index]["path"],
            #     supported,
            #     rpm_table[index]["license"],
            #     rpm_table[index]["signature"],
            #     rpm_table[index]["os-release"],
            #     rpm_table[index]["running"],
            #     rpm.strip(),
            #     "",
            # ]
            row = pd.DataFrame({'name':[rpm_table[index]["name"]],
                                "path": [rpm_table[index]["path"]],
                                "flag_supported": [supported],
                                "license": [rpm_table[index]["license"]],
                                "signature": [rpm_table[index]["signature"]],
                                "os-release": [rpm_table[index]["os-release"]],
                                "running": [rpm_table[index]["running"]],
                                "rpm": [rpm.strip()],
                                "rpm_sig_key": [""]})
            self._driver_df = pd.concat([self._driver_df, row], ignore_index=True
            )

            if self._ssh is None:
                self._progress.console.print(
                    f"[light_steel_blue]Found driver: {rpm_table[index]['path']}[/light_steel_blue]"
                )

    def _org_driver_info(self, driver_files, running_drivers):
        all_infos = driver_files
        files = []
        r_files = []
        for d_info in driver_files:
            fn = d_info.splitlines()[0].strip()
            files.append(fn)

        for r_info in running_drivers:
            r_fn = r_info.splitlines()[0].strip()
            r_files.append(r_fn)
            found = False
            for d_f in files:
                if d_f == r_fn:
                    found = True
                    break
            if not found:
                all_infos.append(r_info)
                files.append(r_fn)

        return all_infos, files, r_files

    def _fill_driver_info(
        self, ip, drivers_modinfo, running_drivers_modinfo, query="all", remote=False
    ):
        drivers_modinfo = self._modinfo_to_list(drivers_modinfo)
        running_drivers_modinfo = self._modinfo_to_list(running_drivers_modinfo)

        all_info, all_files, r_files = self._org_driver_info(
            drivers_modinfo, running_drivers_modinfo
        )
        total_drivers = len(all_files)
        self._task = self._progress.add_task(
            "[italic][bold][green] Working on: "
            + ip
            + "; Total Drivers: "
            + str(total_drivers),
            total=total_drivers,
        )

        rpm_table = []
        for driver in all_info:
            driver = driver.splitlines()
            filename = driver[0].strip()
            name = ""
            supported = []
            suserelease = "Missing"
            running = str(filename in r_files)
            license = ""
            signature = ""

            driver = driver[1:]

            for item in driver:
                values = item.split(":")
                if len(values) < 2:
                    continue

                if values[0] == "supported":
                    supported.append(":".join(values[1:]).strip())
                elif values[0] == "suserelease":
                    suserelease = ":".join(values[1:]).strip()
                elif values[0] == "name":
                    name = ":".join(values[1:]).strip()
                elif values[0] == "license":
                    license = ":".join(values[1:]).strip()
                elif values[0] == "signature":
                    signature = True

            if name == "":
                name = Path(filename).name
            rpm_set = {
                "name": name,
                "path": filename,
                "flag_supported": supported,
                "license": license,
                "signature": signature,
                "os-release": suserelease,
                "running": running,
                "rpm": "",
            }

            rpm_table.append(rpm_set)

        self._driver_df = pd.DataFrame(columns=self._columns)
        self._fill_driver_rpm_info(
            all_files, self._add_row_handler, rpm_table, query, remote
        )

        return self._driver_df
