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
from .data_exporter import SDCConf, ValidLicense


def get_cmd_all_drivers_modinfo():
    return '/usr/sbin/modinfo $(find /lib/modules/ -regex ".*\.\(ko\|ko.xz\|ko.zst\)$") 2>&1'


def get_cmd_all_running_drivers_modinfo():
    return "/usr/sbin/modinfo $(cat /proc/modules | awk '{print $1}') 2>&1"


def async_run_cmd(
    cmd, line_handler, line_handler_arg, start, end, condition, sshClient=None
):
    if sshClient is not None:
        stdin, stdout, stderr = sshClient.exec_command(cmd)

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

        return result
    else:
        cmd_runner = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        result, errs = cmd_runner.communicate()

        return result


class RPMReader:
    def __init__(self, progress):
        self._progress = progress
        self._columns = [
            "name",
            "path",
            "vendor",
            "signature",
            "distribution",
            "license",
            "wm-invoked",
            "df-supported",
            "sym-check",
            "dv-licenses",
            "is-signed",
            "modalias",
        ]

    def _get_driver_alias(self, driver):
        alias = run_cmd("/usr/sbin/modinfo --field=alias %s | grep pci:" % driver)
        return alias.splitlines()
        
    def _get_rpm_modalias(self, rpm):
        modalias = namedtuple("modalias", "kernel_flavor pci_re")
        ml_pci_re = re.compile(r"modalias\((.*):(.*\:.*)\)") # example: modalias(kernel-default:pci:v000019A2d00000712sv*sd*bc*sc*i*)
        ml_all_re = re.compile(r"modalias\((.*):(.*)\)")     # example: packageand(kernel-default:primergy-be2iscsi)
        raw_modalias = run_cmd("rpm -q --supplements %s" %rpm)
        
        alias_re = []
        for line in raw_modalias.splitlines():
            line = str(line, "utf-8").strip()
            pci_rst = ml_pci_re.match(line)
            all_rst = ml_all_re.match(line)
            if pci_rst:
                ker_flavor, pci = pci_rst.groups()
                if "pci:" in pci: # only check PCI devices
                    alias_re.append(pci)
            elif all_rst: # match all (*) should not be allowed
                ker_flavor, rst = all_rst.groups()
                if rst == "*":
                    alias_re.append(rst)
        
        return alias_re
    
    def _driver_symbols_check(self, rpm_symbols, driver):
        symvers = run_cmd("/usr/sbin/modprobe --dump-modversions %s" % driver)

        result = dict()
        result["unfound"] = []
        result["checksum-mismatch"] = []
        for line in symvers.splitlines():
            line = str(line, "utf-8")
            chksum, sym = line.split()
            chksum = hex(int(chksum, base=16))

            req = rpm_symbols.get(sym, None)
            if req is None:
                result["unfound"].append(sym)
                # result.append('Symbol %s not found in rpm requires' % sym)
                continue

            if req.checksum != chksum:
                result["checksum-mismatch"].append(
                    "rpm checksum: %s, driver checksum: %s" % (chksum, req.checksum)
                )
                continue

        return result

    def _get_rpm_symbols(self, rpm):
        KernelSym = namedtuple("KernelSym", "kernel_flavor symbol checksum")
        symver_re = re.compile(r"ksym\((.*):(.*)\) = (.+)")
        raw_symbols = run_cmd("rpm -q --requires %s" % rpm)

        mod_reqs = {}
        for line in raw_symbols.splitlines():
            line = str(line, "utf-8")
            result = symver_re.match(line)
            if result:
                flavor, sym, chksum = result.groups()
                chksum = hex(int(chksum, base=16))
                mod_reqs[sym] = KernelSym(
                    kernel_flavor=flavor, symbol=sym, checksum=chksum
                )

        return mod_reqs

    def _get_driver_supported(self, driver):
        raw_info = run_cmd("/usr/sbin/modinfo %s" % driver)
        raw_info = str(raw_info, "utf-8")
        info_list = raw_info.splitlines()
        supported = ""
        for item in info_list:
            values = item.split(":")
            if len(values) < 2:
                continue

            if values[0].strip() == "supported":
                if supported != "":  # only allow appears once.
                    supported = supported + ", " + ":".join(values[1:]).strip()
                else:
                    supported = ":".join(values[1:]).strip()

        if supported == "":
            return "Missing"
        else:
            return supported

    def _get_driver_license(self, driver):
        raw_info = run_cmd("/usr/sbin/modinfo %s" % driver)
        raw_info = str(raw_info, "utf-8")
        info_list = raw_info.splitlines()
        for item in info_list:
            values = item.split(":")
            if len(values) < 2:
                continue

            if values[0].strip() == "license":
                return ":".join(values[1:]).strip()

        return ""

    def _fmt_driver_supported(self, drivers):
        supported = dict()
        for d in drivers:
            supported[d] = drivers[d]["supported"]

        return supported

    def _fmt_driver_is_signed(self, drivers):
        is_signed = dict()
        for d in drivers:
            is_signed[d] = drivers[d]["is_signed"]
        
        return is_signed

    def _fmt_driver_license(self, drivers):
        licenses = dict()
        for d in drivers:
            licenses[d] = drivers[d]["license"]

        return licenses

    def _fmt_driver_symbol(self, drivers):
        symbols = dict()
        for d in drivers:
            d_info = dict()
            d_info["unfound"] = drivers[d]["symbols"]["unfound"]
            d_info["checksum-mismatch"] = drivers[d]["symbols"]["checksum-mismatch"]
            if len(d_info["unfound"]) == 0 and len(d_info["checksum-mismatch"]) == 0:
                continue
            else:
                symbols[d] = d_info

        return symbols
    
    def _fmt_driver_modalias(self, kmp_alias, drivers):
        key_match_all = 'match_all'
        key_unmatched_km_alias = 'unmatched_km_alias'
        key_unmatched_kmp_alias = 'unmatched_kmp_alias'
        for a in kmp_alias:
            if a == "*":  # "use default-kernel:* to match all the devices is always a bad idea."
                return {key_match_all:True, 
                key_unmatched_km_alias:[], 
                key_unmatched_kmp_alias:[]}
        
        unmatched_ker_alias = []
        unmatched_kmp_alias = kmp_alias.copy()

        for d in drivers:
            for ker_a in drivers[d]["alias"]:
                ker_a = str(ker_a, "utf-8").strip()
                found = False
                for kmp_a in kmp_alias:
                    if fnmatch.fnmatch(ker_a.strip(), kmp_a.strip()):
                        found = True
                        for uk in unmatched_kmp_alias:
                            if uk.strip() == kmp_a.strip():
                                unmatched_kmp_alias.remove(uk)
                                break
                        break
                if not found:
                    unmatched_ker_alias.append(ker_a)
        
        # There has some packages have "%5" in the package but use "_" in the kernel module
        # So we have to match it again, but equal is enough.
        r_ukmpalias = [v.replace("_", "%5F").replace("-", "%2D").replace(".", "%2E") for v in unmatched_ker_alias]
        for i in range(len(unmatched_kmp_alias) - 1, -1, -1):
            found_match = False
            for j in range(len(unmatched_ker_alias) - 1, -1, -1):
                if r_ukmpalias[j] == unmatched_kmp_alias[i]:
                    unmatched_ker_alias.pop(j)
                    found_match = True
            if found_match:
                unmatched_kmp_alias.pop(i)
                
        return {key_match_all:False, 
                key_unmatched_km_alias:unmatched_ker_alias, 
                key_unmatched_kmp_alias:unmatched_kmp_alias}

    def _is_driver_signed(self, driver):
        raw_info = run_cmd("/usr/sbin/modinfo %s" % driver)
        raw_info = str(raw_info, "utf-8")
        info_list = raw_info.splitlines()
        for item in info_list:
            values = item.split(":")
            if len(values) < 2:
                continue

            if values[0].strip() == "signature":
                return True

        return False

    def _driver_checks(self, rpm: str):
        mod_reqs = self._get_rpm_symbols(rpm)

        tmp = tempfile.TemporaryDirectory()

        command = "rpm2cpio %s | cpio -idmv -D %s" % (rpm, tmp.name)
        run_cmd(command)

        rpm_dir = Path(tmp.name)
        files = tuple(rpm_dir.rglob("*.*"))
        drivers = [i for i in files if re.search(r"\.(ko|ko\.xz)$", str(i))]
        result = dict()

        if len(drivers) < 1:
            tmp.cleanup()

            return None

        for driver in drivers:
            item = dict()
            item["symbols"] = self._driver_symbols_check(mod_reqs, driver)
            item["supported"] = self._get_driver_supported(driver)
            item["license"] = self._get_driver_license(driver)
            item["is_signed"] = self._is_driver_signed(driver)
            item["alias"] = self._get_driver_alias(driver)

            dpath = str(driver)
            dpath = dpath[dpath.startswith(tmp.name) + len(tmp.name) - 1 :]
            result[dpath] = item

        tmp.cleanup()

        return result

    def _format_rpm_info(self, rpm_files, raw_output, row_handlers, query="all"):
        raw_output = str(raw_output, "utf-8").split("Name        :")
        rpms = raw_output[1:]
        conf = SDCConf()
        vld_lics = conf.get_valid_licenses()

        style = SDCConf()
        vld_lic = style.get_valid_licenses()
        for i, rpm in enumerate(rpm_files):
            info = rpms[i].splitlines()
            name = info[0].strip()
            signature = ""
            distribution = ""
            vendor = ""
            license = ""
            wm2_invoked = False
            for item in info:
                if (
                    "/usr/lib/module-init-tools/weak-modules2" in item
                    or "debuginfo" in name
                ):
                    wm2_invoked = True

                values = item.split(":")
                if len(values) < 2:
                    continue

                if values[0].strip() == "Signature":
                    signature = ":".join(values[1:]).strip()
                elif values[0].strip() == "Distribution":
                    distribution = ":".join(values[1:]).strip()
                elif values[0].strip() == "Vendor":
                    vendor = ":".join(values[1:]).strip()
                elif values[0].strip() == "License":
                    license = ":".join(values[1:]).strip()

            driver_checks = self._driver_checks(rpm)

            supported = dict()
            symbols = dict()
            d_licenses = dict()
            is_signed = dict()
            km_modalias = dict()
            if driver_checks is not None:
                supported = self._fmt_driver_supported(driver_checks)
                symbols = self._fmt_driver_symbol(driver_checks)
                d_licenses = self._fmt_driver_license(driver_checks)
                is_signed = self._fmt_driver_is_signed(driver_checks)
                km_modalias = self._fmt_driver_modalias(self._get_rpm_modalias(rpm), driver_checks)

            if not self._query_filter(supported, query):
                continue

            for handler in row_handlers:
                handler(
                    [
                        name,
                        rpm,
                        vendor,
                        signature,
                        distribution,
                        license,
                        wm2_invoked,
                        supported,
                        symbols,
                        d_licenses,
                        is_signed, 
                        km_modalias
                    ]
                )

            self._progress.console.print(
                "[bright_black]*********************************************************************[/]"
            )
            self._progress.console.print("name           : %s" % name)
            self._progress.console.print("path           : %s" % rpm)
            self._progress.console.print("vendor         : %s" % vendor)
            if signature == "" or signature == "none" or signature == "(none)":
                self._progress.console.print(
                    "[bold red]signature      : %s[/]" % signature
                )
            else:
                self._progress.console.print("signature      : %s" % signature)
            self._progress.console.print("disturibution  : %s" % distribution)
            self._progress.console.print("license        : %s" % license)
            if wm2_invoked:
                self._progress.console.print("weak module    : %s" % str(wm2_invoked))
            else:
                self._progress.console.print(
                    "[bold red]weak module    : %s[/]" % str(wm2_invoked)
                )
            supt_check = True
            for k in supported:
                if supported[k] != "external":
                    supt_check = False
                    break
            if supt_check:
                self._progress.console.print("supported flag : success")
            else:
                self._progress.console.print(
                    "[bold red]supported flag : failed \n%s[/]" % supported
                )
            sym_check = True
            for k in symbols:
                if len(symbols[k]) != 0:
                    sym_check = False
                    break
            if sym_check:
                self._progress.console.print("symbols checks : success")
            else:
                self._progress.console.print(
                    "[bold red]symbols checks : failed \n%s[/]" % symbols
                )
            license_check = True
            if not ValidLicense(license, vld_lics):
                license_check = False
            else:
                for k in d_licenses:
                    if not ValidLicense(d_licenses[k], vld_lics):
                        license_check = False
                        break

            if license_check:
                self._progress.console.print("license check  : success")
            else:
                self._progress.console.print("[bold red]license check  : failed[/]")

            self._progress.advance(self._task)

    def _query_filter(self, supported, query):
        if query == "all":
            return True
        elif query == "suse" and ": yes" in supported:
            return True
        elif query == "vendor" and ": external" in supported:
            return True
        elif query == "unknow" and (
            ": Missing" in supported or ": Multiple" in supported
        ):
            return True

        return False

    def _add_row(self, row):
        self._rpm_df = self._rpm_df.append(
            pd.Series(row, index=self._columns), ignore_index=True
        )

    def get_rpms_info(self, path, row_handlers=None, query="all"):
        cmd_rpms = "find %s -regextype sed -regex '.*-kmp-.*\.rpm$'" % path
        rpm_files = run_cmd(cmd_rpms)
        rpm_files = str(rpm_files, "utf-8").splitlines()

        self._task = self._progress.add_task(
            "[italic][bold][green] Checking RPMs "
            + "; Total RPMs: "
            + str(len(rpm_files)),
            total=len(rpm_files),
        )

        rpm_infos = run_cmd("rpm -qpi --nosignature --scripts $(%s)" % cmd_rpms)

        if row_handlers is None:
            row_handlers = []

        self._rpm_df = pd.DataFrame(columns=self._columns)
        row_handlers.append(self._add_row)
        self._format_rpm_info(rpm_files, rpm_infos, row_handlers, query)

        return self._rpm_df

    def get_rpm_info(self, rpmfile):
        self._rpm_df = pd.DataFrame(columns=self._columns)
        rpm_infos = run_cmd("rpm -qpi --nosignature --scripts %s" % rpmfile)
        self._task = self._progress.add_task(
            "[italic][bold][green] Checking RPMs " + "; Total RPMs: 1 ",
            total=1,
        )

        self._format_rpm_info([rpmfile.name], rpm_infos, [self._add_row])

        return self._rpm_df


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
            result = str(result, "utf-8")

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

        rpmInfo = str(rpmInfo, "utf-8").split("Name        :")
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
