import pandas as pd
from ..config import SDCConf
from pathlib import Path
import fnmatch
from enum import Enum, unique
from ..config import SDCConf


def kms_to_dataframe(data):
    df = pd.DataFrame()

    for item in data:
        new_row = pd.Series({
            "level"           : item["level"],
            "name"            : item["name"],
            "path"            : item["path"],
            "vendor"          : item["vendor"],
            "signature"       : item["signature"],
            "license"         : item["license"],
            "wm2_invoked"     : item["wm2_invoked"],
            "supported_flag"  : item["km"]["supported"],
            "km_signatures"   : item["km"]["signature"],
            "km_licenses"     : item["km"]["license"],
            "symbols"         : item["km"]["symbols"],
            "modalias"        : item["km"]["alias"]
            })
        df = pd.concat([df, new_row.to_frame().T], ignore_index=True)

    return df


@unique
class KMEvaluation (Enum):
    PASS = 1
    WARNING = 2
    ERROR = 3

class KMAnalysis:
    def __init__(self):
        conf = SDCConf()
        self._valid_licenses = conf.get_valid_licenses()

    def kmp_analysis(self, data):
        ana_level = []
        name_lev, name_anls = self._kmp_name_analysis(data["name"])
        ana_level.append(name_lev.value)
        path_lev, path_anls = self._kmp_path_analysis(data["path"])
        ana_level.append(path_lev.value)
        ven_lev, vendor_anls = self._kmp_vendor_analysis(data["vendor"])
        ana_level.append(ven_lev.value)
        sig_lev, sig_anls = self._kmp_vendor_analysis(data["signature"])
        ana_level.append(ven_lev.value)
        lic_lev, license_anls = self._licenses_analysis([data["license"]])
        ana_level.append(lic_lev.value)
        level, wm2_invoked_anls = self._kmp_wm2_invoked_analysis(data["wm2_invoked"])
        ana_level.append(level.value)
        km_lev, km_anls = self._kmp_km_analysis(data["reqs"], data["modalias"], data["km_info"])
        ana_level.append(km_lev.value)
        
        return {
            "level"      : KMPEvaluation(max(ana_level)),
            "name"       : {"level": name_lev, "value": name_anls},
            "path"       : {"level": path_lev, "value": path_anls},
            "vendor"     : {"level": ven_lev,  "value": vendor_anls},
            "signature"  : {"level": sig_lev,  "value": sig_anls},
            "license"    : {"level": lic_lev,  "value": license_anls},
            "wm2_invoked": {"level": lic_lev,  "value": wm2_invoked_anls},
            "km"         : km_anls
        }

    def _kmp_name_analysis(self, name):
        return KMPEvaluation.PASS, name

    def _kmp_path_analysis(self, path):
        return KMPEvaluation.PASS, path

    def _kmp_vendor_analysis(self, vendor):
        if vendor == "":
            return KMPEvaluation.WARNING, "Vendor should not be empty"
        
        return KMPEvaluation.PASS, vendor

    def _kmp_signature_analysis(self, signature):
        if signature == "" or signature is None:
            return KMPEvaluation.WARNING, "Signature should not be empty"
        
        return KMPEvaluation.PASS, signature

    def _licenses_analysis(self, licenses: list):
        if len(licenses) < 1 or (len(licenses) == 1 and licenses[0] == ""):
            return KMPEvaluation.WARNING, "No License found in KMP"

        invlics = licenses.copy()
        for vlic in self._valid_licenses:
            for lic in invlics:
                if lic == vlic.get("name"):
                    invlics.remove(lic)
        
        if len(invlics) == 0:
            return KMPEvaluation.PASS, " ".join(licenses)
        
        return KMPEvaluation.WARNING, "Invalid or non Opensource license found: %s" % " ".join(invlics)

    def _kmp_wm2_invoked_analysis(self, wm2):
        if wm2:
            return KMPEvaluation.PASS, wm2
        
        return KMPEvaluation.ERROR, wm2

    def _kmp_km_ana_summary(self, km_info, flavor):
        summary = {"level": KMPEvaluation.PASS, "value": ""}
        values = []
        for km_path in km_info:
            km_data = km_info.get(km_path)
            level = km_data[flavor].get("level")
            msg = km_data[flavor].get("value")
            
            summary["level"] = KMPEvaluation(max(summary["level"].value, level.value))
            values.append(msg)
        
        summary["value"] = " ".join(set(values))
                
        return summary
        
    def _kmp_km_analysis(self, kmp_reqs, kmp_modalias, km_info):
        km_analysis = {}
        ana_level = []
        for km_path in km_info:
            km_analysis[km_path] = {}
            eval, msg = self._licenses_analysis(km_info.get(km_path)["license"])
            km_analysis[km_path]["license"] = {"level": eval, "value": msg}
            ana_level.append(eval.value)
            
            eval, msg = self._km_supported_analysis(km_info.get(km_path)["supported"])
            if eval != KMPEvaluation.PASS:
                msg = f"{Path(km_path).name}: {msg}"
            km_analysis[km_path]["supported"] = {"level": eval, "value": msg}
            ana_level.append(eval.value)
            
            eval, msg = self._km_signature_analysis(km_info.get(km_path)["signature"])
            km_analysis[km_path]["signature"] = {"level": eval, "value": msg}
            ana_level.append(eval.value)
        
            eval, msg = self._kms_symbols_analysis(kmp_reqs, km_info.get(km_path)["symbols"])
            km_analysis[km_path]["symbols"] = {"level": eval, "value": msg}
            ana_level.append(eval.value)    

        eval, alaias_msg = self._kms_modalias_analysis(kmp_modalias, km_info)
        ana_level.append(eval.value)

        ana_summary = {"license"  : self._kmp_km_ana_summary(km_analysis, "license"),
                       "supported": self._kmp_km_ana_summary(km_analysis, "supported"),
                       "signature": self._kmp_km_ana_summary(km_analysis, "signature"),
                       "symbols"  : {"level": eval, "value": alaias_msg},
                       "alias"    : self._kmp_km_ana_summary(km_analysis, "symbols")}
        return KMPEvaluation(max(ana_level)), ana_summary

    def _kms_symbols_analysis(self, kmp_reqs, km_syms):
        syms = {}
        syms["unfound"] = []
        syms["checksum-mismatch"] = []
        for sym in km_syms:
            chksum = km_syms.get(sym)
            chksum = hex(int(chksum, base=16))

            req = kmp_reqs.get(sym, None)
            if req is None:
                syms["unfound"].append(sym)
                continue

            if req.checksum != chksum:
                syms["checksum-mismatch"].append(
                    "rpm checksum: %s, driver checksum: %s" % (chksum, req.checksum)
                )

        unfounded = len(syms["unfound"])
        mismatched = len(syms["checksum-mismatch"])
        if unfounded == 0 and mismatched == 0:
            return KMPEvaluation.PASS, "All passed"
        
        msg = ""
        if unfounded > 0:
            msg = f"Number of symbols can not be found in KMP: {unfounded} "

        if mismatched > 0:
            msg = msg + f"Number of symbols checksum does not match: {mismatched}"

        return KMPEvaluation.ERROR, msg.strip()

    def _kms_modalias_analysis(self, kmp_modalias, km_info):
        for a in kmp_modalias:
            if a == "*":  # "use default-kernel:* to match all the devices is always a bad idea."
                return KMPEvaluation.ERROR, "KMP can match all the devices! Highly not recommended!"

        kms_alias = []
        for km_path in km_info:
            kms_alias += km_info.get(km_path)["alias"]
        kms_alias = set(kms_alias)
        unmatched_ker_alias = []
        unmatched_kmp_alias = kmp_modalias.copy()

        for ker_a in kms_alias:
            ker_a = ker_a.strip()
            found = False
            for kmp_a in kmp_modalias:
                if fnmatch.fnmatch(ker_a.strip(), kmp_a.strip()):
                    found = True
                    for uk in unmatched_kmp_alias:
                        if uk.strip() == kmp_a.strip():
                            unmatched_kmp_alias.remove(uk)
                            break
                    break
            if not found:
                unmatched_ker_alias.append(ker_a)

        if len(unmatched_ker_alias) == 0 and len(unmatched_kmp_alias) == 0:
            return KMPEvaluation.PASS, "All passed"

        msg = ""
        if len(unmatched_ker_alias) > 0:
            msg += "Alias found in kernel module but no match in it's package: "
            for kmu in unmatched_ker_alias:
                msg += kmu + ", "
            msg += "\n"
        
        if len(unmatched_kmp_alias) > 0:
            msg += "Alias found in the package but no match in it's kernel module: "
            for kmpu in unmatched_kmp_alias:
                msg += kmpu + ", "

        return KMPEvaluation.ERROR, msg

    def _km_signature_analysis(self, signature):
        if str(signature) != "":
            return KMPEvaluation.PASS, "Exist"
        
        return KMPEvaluation.ERROR, "No signature found"        

    def _km_supported_analysis(self, values):
        if len(values) < 1:
            return KMPEvaluation.ERROR, "No 'supported' flag found"
        
        if len(values) == 1 and values[0] == "external":
            return KMPEvaluation.PASS, ""
        
        return KMPEvaluation.ERROR, "Multiple values found, they're %s" % " ".join(values)
