
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
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from ..config import SDCConf
from enum import Enum, unique
from .utils.cmd import run_cmd


@unique
class KMEvaluation (Enum):
    PASS = 1
    WARNING = 2
    ERROR = 3

class KMAnalysis:
    def __init__(self):
        conf = SDCConf()
        self._valid_licenses = conf.get_valid_licenses()
    
    def kms_analysis(self, kms):
        row_level = []
        df = pd.DataFrame()
        for filename in kms:
            lev_name, name = self._km_module_name_analysis(kms[filename].get("name", ""))
            row_level.append(lev_name.value)
            lev_fn, filename = self._km_filename_analysis(filename, kms[filename].get("weak-updates", 0))
            row_level.append(lev_fn.value)
            lev_spd, supported = self._km_supported_analysis(kms[filename].get("supported", ""))
            row_level.append(lev_spd.value)
            lev_lic, license = self._km_license_analysis(kms[filename].get("license", ""))
            row_level.append(lev_lic.value)
            lev_sig, signature = self._km_signature_analysis(kms[filename].get("signature", ""))
            row_level.append(lev_sig.value)
            lev_r, running = self._km_running_analysis(kms[filename].get("running", ""))
            row_level.append(lev_r.value)
            lev_kmp, kmp = self._km_kmp_analysis(kms[filename].get("kmp", None))
            
            row = pd.Series({
                             "level": KMEvaluation(max(row_level)),
                             "modulename": name,
                             "filename": filename,
                             "license": license,
                             "signature": signature,
                             "supported": " ".join(supported),
                             "running": running,
                             "kmpname": kmp["name"],
                             "kmp_signature": kmp["signature"]})
            
            df = pd.concat([df, row.to_frame().T], ignore_index=True)
        
        return df
    
    def _km_module_name_analysis(self, name):
        return KMEvaluation.PASS, name
    
    def _km_filename_analysis(self, filename, wu):
        lev = KMEvaluation.PASS
        if not filename.startswith("/lib/modules"):
            lev = KMEvaluation.WARNING
        
        if wu != 0: # under weak-updates folder.
            if wu == 2 or wu == 3: # kernel module does not exist or not a link
                lev = KMEvaluation.ERROR
        
        return lev, filename
    
    def _km_supported_analysis(self, supported):
        sps = supported.splitlines()
        lev = KMEvaluation.PASS
        # no supported flag or 1 supported flag but the value is not yes(supported by SUSE) or supported (supported by others).
        if len(sps) == 0 or (len(sps) == 1 and (sps[0] != "yes" or sps[0] != "supported")):
            lev = KMEvaluation.ERROR
        elif len(sps) > 1:
            lev = KMEvaluation.WARNING
            for v in sps:
                if v != "yes" or v != "external":
                    lev = KMEvaluation.ERROR
                    break

        return lev, sps
    
    def _km_license_analysis(self, license):
        if license in self._valid_licenses:
            return KMEvaluation.PASS, license
        
        return KMEvaluation.WARNING, license
    
    def _km_signature_analysis(self, signature):
        if signature != "":
            return KMEvaluation.PASS, signature
        else:
            return KMEvaluation.WARNING, signature
    
    def _km_running_analysis(self, running):
        return KMEvaluation.PASS, running
    
    def _km_kmp_analysis(self, kmp):
        if None == kmp:
            return KMEvaluation.PASS, {"name": "", "signature": ""} 

        name = kmp["name"]
        signature = kmp["signature"]
        
        if name.endswith("is not owned by any package"):
            return KMEvaluation.WARNING, kmp
        elif signature == "":
            return KMEvaluation.WARNING, kmp
        
        return KMEvaluation.PASS, kmp


class KMReader:
    # resolve OSError: [Errno 7] Argument list too long: '/bin/sh'
    def _split_cmd_args(self, files, cmd):
        files_no = len(files)
        output = ""
        for i in range(0, files_no, 300):
            curr_slip = 300
            if i + 300 > files_no:
                curr_slip = files_no - i
            str_files = "\n".join(files[i:i+curr_slip])
            output += run_cmd(cmd % str_files)

        return output

    def get_all_modinfo(self):
        running_kms = run_cmd("/usr/sbin/modinfo $(cat /proc/modules | awk '{print $1}') | grep filename | awk '{print$2}'").splitlines()
        lm_kms = run_cmd("find /lib/modules/ -regex \".*\.\(ko\|ko.xz\|ko.zst\)$\"").splitlines()
        
        files = list(set(running_kms + lm_kms))
        # we don't need the entire signature, so add grep to ignore the details in other lines.
        kms_info = self._split_cmd_args(files, '/usr/sbin/modinfo %s | grep -E "^([a-z]|[A-Z])" 2>&1')
        kms_info = kms_info.split("filename:")
        if len(kms_info) == 0:
            return {}
        
        kms = {}
        kmps = self._split_cmd_args(files, 'rpm -qf %s')
        kmps = kmps.splitlines()
        kmps_sig_pair = self._get_kmps_signature(kmps)
        # Here's something needs to be take care of if you split all the modinfo output by "filename",
        # If the kernel module is an invalid link, the output is:
        # modinfo: ERROR: Module invalid-link.ko not found.
        # If the kernel module is not a link but a broken kernel module, the output is:
        # filename:       /full/path/to/broken.ko
        # modinfo: ERROR: could not get modinfo from 'broken': Invalid argument
        # so if you want to match the KMP search index with the modinfo output index, you have to
        # take care of above.
        kmp_index = 0
        for km_info in kms_info[1:]: # first one is empty.
            lines = km_info.splitlines()
            info = {}
            filename = lines[0].strip()
            for line in lines[1:]: # first line is filename, and filename is the key for info.
                vs = line.split(":")
                k, v = vs[0].strip(), ":".join(vs[1:]).strip()
                if "modinfo" == k: # invalid kernel module found
                    if "not found." in v: # invalid kernel module link found
                        file = files[kmp_index]  # the full file path only can be found in files. The orders are the same.
                        kmps[file]["rpm"] = {"name": kmps[kmp_index], "signature": ""}
                        kmp_index += 1
                elif None != info.get(k, None): # if already exist
                    info[k] = info[k] + "\n" + v
                else:
                    info[k] = v
            kms[filename]            = info
            kms[filename]["running"] = filename in running_kms
            kms[filename]["rpm"]     = {"name": kmps[kmp_index], "signature": kmps_sig_pair.get(kmps[kmp_index], "")}
            kmp_index += 1
        
        self._check_weak_links(kms)
        
        return kms

    def _check_weak_links(self, kms):
        pkg_path = os.path.dirname(__file__)
        script = f"{pkg_path}/utils/scripts/check-links.sh"
        j_links = run_cmd(script)
        links = json.loads(j_links)
        for km in links["weak-updates"]:
            filename = km.get("km", None)
            if None != filename:
                kms[filename]["weak-updates"] = km.get("status", 0)
    
    def _get_kmps_signature(self, kmps):
        uniq_kmps = set(kmps)
        invalid_kmps = []
        for kmp in uniq_kmps:
            if kmp.endswith("is not owned by any package"):
                invalid_kmps.append(kmp)
        for ik in invalid_kmps:
            uniq_kmps.remove(ik)
        
        signatures = run_cmd(f'rpm -q --info {" ".join(uniq_kmps)} | grep -E "^Signature"').splitlines() # example: Signature   : RSA/SHA256, Wed 12 Oct 2022 06:57:49 PM CST, Key ID 70af9e8139db7c82
        
        kmp_sig_pairs = {}
        uniq_kmps = list(uniq_kmps)
        for i in range(0, len(uniq_kmps)):
            kmp_sig_pairs[uniq_kmps[i]] = signatures[i].split(":")[1:]
        
        return kmp_sig_pairs
        

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
