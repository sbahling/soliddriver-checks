import os
import pandas as pd
import json
from ..config import SDCConf
from enum import Enum, unique
from .utils.cmd import run_cmd
import requests


@unique
class KMEvaluation (Enum):
    PASS = 1
    WARNING = 2
    ERROR = 3

    def __str__(self):
        return self.name

    def __int__(self):
        return self.value

    def to_json(self):
        return {'level': self.name, 'value': self.value}


class KMAnalysis:
    def __init__(self):
        conf = SDCConf()
        self._valid_licenses = conf.get_valid_licenses()
        self._valid_licenses = [i.get('name', '') for i in self._valid_licenses]

    def kms_analysis(self, kms):
        row_level = []
        df = pd.DataFrame()
        for filename in kms:
            lev_name, name = self._km_module_name_analysis(kms[filename].get("name", ""))
            row_level.append(lev_name['value'])
            lev_fn, filename = self._km_filename_analysis(filename, kms[filename].get("weak-updates", 0))
            row_level.append(lev_fn['value'])
            lev_spd, supported = self._km_supported_analysis(kms[filename].get("supported", ""))
            row_level.append(lev_spd['value'])
            lev_lic, license = self._km_license_analysis(kms[filename].get("license", ""))
            row_level.append(lev_lic['value'])
            lev_sig, signature = self._km_signature_analysis(kms[filename].get("signature", ""))
            row_level.append(lev_sig['value'])
            lev_r, running = self._km_running_analysis(kms[filename].get("running", ""))
            row_level.append(lev_r['value'])
            lev_kmp, kmp = self._km_kmp_analysis(kms[filename].get("kmp", None))
            row_level.append(lev_kmp['value'])

            row = pd.Series({
                             "level": KMEvaluation(max(row_level)).to_json(),
                             "modulename": {"level": lev_name, "value": name},
                             "filename": {"level": lev_fn, "value": filename},
                             "license": {"level": lev_lic, "value": license},
                             "signature": {"level": lev_sig, "value": signature},
                             "supported": {"level": lev_spd, "value": " ".join(supported).strip()},
                             "running": {"level": lev_r, "value": running},
                             "kmp": {"level": lev_kmp, "value": kmp}
                             })

            df = pd.concat([df, row.to_frame().T], ignore_index=True)

        return df

    def _km_module_name_analysis(self, name):
        return KMEvaluation.PASS.to_json(), name

    def _km_filename_analysis(self, filename, wu):
        lev = KMEvaluation.PASS
        if not filename.startswith("/lib/modules"):
            lev = KMEvaluation.WARNING

        if wu != 0:  # under weak-updates folder, and have issues.
            if wu == 2 or wu == 3:  # kernel module does not exist or not a link
                lev = KMEvaluation.ERROR

        return lev.to_json(), filename

    def _km_supported_analysis(self, supported):
        sps = supported.splitlines()
        lev = KMEvaluation.PASS
        # no supported flag or 1 supported flag but the value is not yes(supported by SUSE) or supported (supported by others).
        if len(sps) == 0 or (len(sps) == 1 and sps[0] != "yes" and sps[0] != "no" and sps[0] != "external"):
            lev = KMEvaluation.ERROR
        elif len(sps) > 1:
            lev = KMEvaluation.WARNING
            for v in sps:
                if v != "yes" and v != "no" and v != "external":
                    lev = KMEvaluation.ERROR
                    break

        return lev.to_json(), sps

    def _km_license_analysis(self, license):
        lev = KMEvaluation.PASS

        lics = license.split('\n')
        for i in lics:
            if i not in self._valid_licenses:
                lev = KMEvaluation.WARNING
                break

        return lev.to_json(), license

    def _km_signature_analysis(self, signature):
        if signature != "":
            return KMEvaluation.PASS.to_json(), "Yes"
        else:
            return KMEvaluation.WARNING.to_json(), "No"

    def _km_running_analysis(self, running):
        return KMEvaluation.PASS.to_json(), running

    def _km_kmp_analysis(self, kmp):
        if kmp is None:
            return KMEvaluation.PASS.to_json(), {"name": "", "signature": ""} 

        name = kmp["name"]
        signature = kmp["signature"]

        if name.endswith("is not owned by any package"):
            return KMEvaluation.WARNING.to_json(), "Not owned by any package"
        elif signature == "":
            return KMEvaluation.WARNING.to_json(), name + ": has no signature"

        return KMEvaluation.PASS.to_json(), name


class KMReader:
    # resolve OSError: [Errno 7] Argument list too long: '/bin/sh'
    def _split_cmd_args(self, files, cmd):
        files_no = len(files)
        output = ""
        step = 300
        for i in range(0, files_no, step):
            curr_slip = step
            if i + step > files_no:
                curr_slip = files_no - i
            str_files = " ".join(files[i:i+curr_slip])
            output += run_cmd(cmd % str_files)

        return output

    def get_all_modinfo(self):
        running_kms = run_cmd("/usr/sbin/modinfo $(cat /proc/modules | awk '{print $1}') | grep filename | awk '{print$2}'").splitlines()
        # Have to remove the invalid running kernel module, like it's running inside container.
        # But it always can't get rpm information if it's running inside container.
        running_kms = [file for file in running_kms if not file.startswith("modinfo: ERROR:")]
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
        # take care of above. This is what I am doing.
        kmp_index = 0
        for km_info in kms_info[1:]:  # first one is empty.
            lines = km_info.splitlines()
            info = {}
            filename = lines[0].strip()
            for line in lines[1:]:  # first line is filename, and filename is the key for info.
                vs = line.split(":")
                k, v = vs[0].strip(), ":".join(vs[1:]).strip()
                if "modinfo" == k:  # invalid kernel module found
                    if "not found." in v:  # invalid kernel module link found
                        file = files[kmp_index]  # the full file path only can be found in files. The orders are the same.
                        kmps[file]["rpm"] = {"name": kmps[kmp_index], "signature": ""}
                        kmp_index += 1
                elif info.get(k, None) is not None:  # if already exist
                    info[k] = info[k] + "\n" + v
                else:
                    info[k] = v
            kms[filename]            = info
            kms[filename]["running"] = filename in running_kms
            kms[filename]["kmp"]     = {"name": kmps[kmp_index], "signature": kmps_sig_pair.get(kmps[kmp_index], "")}
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
            if filename is not None:
                kms[filename]["weak-updates"] = km.get("status", 0)

    def _get_kmps_signature(self, kmps):
        uniq_kmps = set(kmps)
        invalid_kmps = []
        for kmp in uniq_kmps:
            if kmp.endswith("is not owned by any package"):
                invalid_kmps.append(kmp)
        for ik in invalid_kmps:
            uniq_kmps.remove(ik)
        # example: Signature   : RSA/SHA256, Wed 12 Oct 2022 06:57:49 PM CST, Key ID 70af9e8139db7c82
        signatures = run_cmd(f'rpm -q --info {" ".join(uniq_kmps)} | grep -E "^Signature"').splitlines()

        kmp_sig_pairs = {}
        uniq_kmps = list(uniq_kmps)
        for i in range(0, len(uniq_kmps)):
            kmp_sig_pairs[uniq_kmps[i]] = signatures[i].split(":")[1:]

        return kmp_sig_pairs


def read_remote_json(url):
    response = requests.get(url)
    df = pd.read_json(response.text)

    return df
