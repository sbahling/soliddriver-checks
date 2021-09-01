from numpy import c_
from numpy.core.fromnumeric import shape
import pdfkit
import pandas as pd
import os
from pathlib import Path
import dominate
from dominate.tags import html, body, h1, div, tr, td, th, table, style, ul, li, p
from dominate.util import raw
from openpyxl.styles import (
    PatternFill,
    Font,
    Border,
    Side,
    Alignment,
    NamedStyle,
    borders,
)
from openpyxl.styles.differential import DifferentialStyle
from openpyxl import load_workbook
from openpyxl.formatting.rule import Rule
from openpyxl.utils.dataframe import dataframe_to_rows
import json
import ast
import string
from openpyxl import Workbook
import time
from jinja2 import Environment, FileSystemLoader
import re
from copy import copy


class SDCConf:
    def __init__(self):
        pkg_path = os.path.dirname(__file__)
        cfg_path = f"{pkg_path}/../config/soliddriver-checks.conf"

        with open(cfg_path, "r") as fp:
            self._conf = json.load(fp)

    def _get_xlsx_info(self, *locs):
        conf = self._conf
        for loc in locs:
            conf = conf[loc]

        font = Font(
            name=conf["font"]["family"],
            size=conf["font"]["size"],
            bold=conf["font"]["bold"],
            color=conf["font"]["color"],
        )
        sd = Side(
            border_style=conf["side"]["border_style"], color=conf["side"]["color"]
        )
        bd = Border(top=sd, left=sd, right=sd, bottom=sd)
        fill = PatternFill(
            start_color=conf["fill"]["bgcolor"],
            end_color=conf["fill"]["bgcolor"],
            fill_type="solid",
        )

        return font, bd, fill

    def get_valid_licenses(self):
        return self._conf["valid-licenses"]

    def get_rpm_xslx_table_header(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "header")

    def get_rpm_xslx_table_normal(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "data", "normal")

    def get_rpm_xslx_table_important_failed(self):
        return self._get_xlsx_info(
            "rpm-check", "excel", "table", "data", "important-failed"
        )

    def get_rpm_xslx_table_critical_failed(self):
        return self._get_xlsx_info(
            "rpm-check", "excel", "table", "data", "critical-failed"
        )

    def get_rpm_xslx_table_great_row(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "row", "great")

    def get_rpm_xslx_table_warn_row(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "row", "warn")

    def get_driver_html_warn_critical(self):
        return self._conf["driver-check"]["html"]["critical_failed"]

    def get_driver_sig_keys(self):
        return self._conf["driver-check"]["sig-keys"]

    def get_driver_html_warn_important(self):
        return self._conf["driver-check"]["html"]["important_failed"]

    def get_driver_xslx_table_header(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "header")

    def get_driver_xslx_table_normal(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "data", "normal")

    def get_driver_xslx_table_important_failed(self):
        return self._get_xlsx_info(
            "driver-check", "excel", "table", "data", "important-failed"
        )

    def get_driver_xslx_table_critical_failed(self):
        return self._get_xlsx_info(
            "driver-check", "excel", "table", "data", "critical-failed"
        )

    def get_driver_xslx_table_warn_row(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "row", "warn")


def ValidLicense(license, licenses):
    for lic in licenses:
        if lic["name"] == license:
            return True

    return False


class ExcelTemplate:
    def __init__(self):
        pkg_path = os.path.dirname(__file__)
        self._cfg_path = f"{pkg_path}/../config/templates/templates.xlsx"

    def set_driver_check_overview(self, ws):
        self._copy_work_sheep("driver-check-summary", ws)

    def set_rpm_check_overview(self, ws):
        self._copy_work_sheep("rpm-check-summary", ws)

    def _copy_work_sheep(self, title, ws):
        tmpl = load_workbook(filename=self._cfg_path)
        cover = tmpl[title]

        ws.title = "Overview"
        for row in cover.rows:
            for cell in row:
                ws[cell.coordinate].value = copy(cell.value)
                # ws[cell.coordinate].style = copy(cell.style)
                ws[cell.coordinate].font = copy(cell.font)
                ws[cell.coordinate].border = copy(cell.border)
                ws[cell.coordinate].fill = copy(cell.fill)
                ws[cell.coordinate].alignment = copy(cell.alignment)


class RPMsExporter:
    def __init__(self, logger):
        self._logger = logger
        self._style = SDCConf()

    def _summary_symbol_result(self, val):
        unfound_no = len(val["unfound"])
        cs_mm_no = len(val["checksum-mismatch"])
        if unfound_no == 0 and cs_mm_no == 0:
            return ""

        result = ""
        if unfound_no > 0:
            result = "Can not find symbols like {} ... in RPM! ".format(
                val["unfound"][0]
            )

        if cs_mm_no > 0:
            result = (
                result
                + "Symbols check sum like {} ... does not match in RPM!".format(
                    val["checksum-mismatch"][0]
                )
            )

        return result

    def _get_sym_check_failed(self, val):
        result = ""
        for driver in val:
            summary = self._summary_symbol_result(val[driver])
            if summary != "":
                result = result + "Found {} has below issue(s):\n  {}\n".format(
                    Path(driver).name, summary
                )

        return result

    def _get_supported_driver_failed(self, supported):
        failed_drivers = []
        for driver in supported:
            if supported[driver] != "external":
                d_name = Path(driver).name
                failed_drivers.append(f"{d_name} : {supported[driver]}")

        return failed_drivers

    def _get_summary_table(self, rpm_table):
        df = rpm_table.copy()

        df["sym-check"] = df["sym-check"].astype(str)

        df.loc[df["sym-check"].str.contains("ko"), "sym-check"] = "failed"

        vendors = df["vendor"].unique()
        df_summary = pd.DataFrame(
            columns=[
                "Vendor",
                "Total rpms",
                "Supported:external",
                "License",
                "Signature",
                "Weak Module Invoked",
                "Symbols Check Failed",
            ]
        )

        def external_count(supported_flag):
            num = 0
            for sf in supported_flag:
                misMatch = False
                for driver in sf:
                    if sf[driver] != "external":
                        misMatch = True
                        break

                if not misMatch:
                    num += 1

            return num

        def license_check(vld_lics, rpm_licenses, driver_license):
            count = 0
            for idx, rl in rpm_licenses.items():
                if ValidLicense(rl, vld_lics):
                    count += 1
                else:
                    d_lics = driver_license[idx]
                    for dl in d_lics:
                        if ValidLicense(dl, vld_lics):
                            count += 1
                            break

            return count

        vld_lic = self._style.get_valid_licenses()

        for v in vendors:
            df_vendor = df.loc[df["vendor"] == v]
            total = len(df_vendor.index)
            external = external_count(df_vendor["df-supported"])
            failed = len(
                df_vendor.loc[df_vendor["sym-check"] == "failed", "sym-check"].index
            )
            lic_check = license_check(
                vld_lic, df_vendor["license"], df_vendor["dv-licenses"]
            )
            no_sig = len(df_vendor.loc[df_vendor["signature"] != "", "signature"].index)
            wm_invoked = len(df_vendor.loc[df_vendor["wm-invoked"], "wm-invoked"].index)
            # if it's a debug rpm, it doesn't need to invoke wm module, so just add it to 
            # the invoked list.
            wm_invoked += len(df_vendor.loc[df["name"].str.contains("debuginfo"), "name"].index)
            df_summary = df_summary.append(
                {
                    "Vendor": v,
                    "Total rpms": total,
                    "Supported:external": f"{external} ({external/total * 100:.2f}%)",
                    "License": f"{lic_check} ({lic_check/total * 100:.2f}%)",
                    "Signature": f"{no_sig} ({no_sig/total * 100:.2f}%)",
                    "Weak Module Invoked": f"{wm_invoked} ({wm_invoked/total * 100:.2f}%)",
                    "Symbols Check Failed": f"{failed} ({failed/total * 100:.2f}%)",
                },
                ignore_index=True,
            )

        return df_summary

    def _get_summary_table_html(self, rpm_table):
        tb = table()
        with tb:
            tb.set_attribute("class", "summary_table")
            df_summary = self._get_summary_table(rpm_table)
            with tr():
                cols = df_summary.columns
                for col in cols:
                    if col == "vendor":
                        t = th(col)
                        t.set_attribute("class", "summary_vendor")
                    else:
                        th(col)

                for i, row in df_summary.iterrows():
                    vendor = row["Vendor"]
                    total_rpms = row["Total rpms"]
                    s_external = row["Supported:external"]
                    lic_check = row["License"]
                    signature = row["Signature"]
                    wm_invoked = row["Weak Module Invoked"]
                    sym_failed = row["Symbols Check Failed"]

                    row_passed = False
                    if (
                        vendor != ""
                        and int(s_external.split(" ")[0]) == total_rpms
                        and int(lic_check.split(" ")[0]) == total_rpms
                        and int(signature.split(" ")[0]) == total_rpms
                        and int(wm_invoked.split(" ")[0]) == total_rpms
                        and int(sym_failed.split(" ")[0]) == 0
                    ):
                        row_passed = True
                    with tr() as r:
                        if row_passed:
                            r.set_attribute("class", "summary_great_row")
                        if vendor != "":
                            td(vendor)
                        else:
                            tv = td("no vendor information")
                            tv.set_attribute("class", "important_failed")
                        with td(total_rpms) as t:
                            t.set_attribute("class", "summary_total")
                        with td(s_external) as t:
                            if int(s_external.split(" ")[0]) != total_rpms:
                                t.set_attribute(
                                    "class", "critical_failed summary_number"
                                )
                            else:
                                t.set_attribute("class", "summary_number")
                        with td(lic_check) as t:
                            if int(lic_check.split(" ")[0]) != total_rpms:
                                t.set_attribute(
                                    "class", "important_failed summary_number"
                                )
                            else:
                                t.set_attribute("class", "summary_number")
                        with td(signature) as t:
                            if int(signature.split(" ")[0]) != total_rpms:
                                t.set_attribute(
                                    "class", "important_failed summary_number"
                                )
                            else:
                                t.set_attribute("class", "summary_number")
                        with td(wm_invoked) as t:
                            if int(wm_invoked.split(" ")[0]) != total_rpms:
                                t.set_attribute(
                                    "class", "critical_failed summary_number"
                                )
                            else:
                                t.set_attribute("class", "summary_number")
                        with td(sym_failed) as t:
                            if int(sym_failed.split(" ")[0]) != 0:
                                t.set_attribute(
                                    "class", "critical_failed summary_number"
                                )
                            else:
                                t.set_attribute("class", "summary_number")

        return tb

    def _rename_rpm_detail_columns(self, rpm_table):
        df = rpm_table.copy()
        df = df.rename(
            columns={
                "name": "Name",
                "path": "Path",
                "vendor": "Vendor",
                "signature": "Signature",
                "distribution": "Distribution",
                "license": "License",
                "wm-invoked": "Weak Module Invoked",
                "df-supported": "Driver Flag: Supported",
                "sym-check": "Symbols Check",
                "dv-licenses": "Driver Licenses",
            }
        )

        return df

    def _fmt_driver_license_check(self, rpm_license, driver_licenses, vld_lics):
        chk_result = ""
        if not ValidLicense(rpm_license, vld_lics):
            chk_result = f"RPM license doesn't supported: {rpm_license}"
            return chk_result

        un_supported_driver = dict()
        for key in driver_licenses:
            if not ValidLicense(driver_licenses[key], vld_lics):
                un_supported_driver[key] = driver_licenses[key]

        if len(un_supported_driver) == 0:
            return chk_result
        else:
            chk_result = "Driver licenses are not supported!\n"
            for idx, key in enumerate(un_supported_driver):
                if idx > 2:  # only show 3 result is enough, keep the table clear.
                    chk_result = f"{chk_result} ..."
                    break
                chk_result = (
                    f"{chk_result} {Path(key).name} : {un_supported_driver[key]}\n"
                )

        return chk_result

    def _get_table_detail_html(self, rpm_table):
        df = self._rename_rpm_detail_columns(rpm_table)
        tb = table()
        vld_lic = self._style.get_valid_licenses()
        with tb:
            tb.set_attribute("class", "table_center")
            with tr():
                cols = df.columns
                for idx, col in enumerate(cols):
                    if col != "Driver Licenses":  # Don't show this column
                        t = th(col)
                        t.set_attribute("class", f"detail_{idx}")

            for i, row in df.iterrows():
                with tr() as r:
                    name = row["Name"]
                    path = row["Path"]
                    vendor = row["Vendor"]
                    signature = row["Signature"]
                    distribution = row["Distribution"]
                    license = row["License"]
                    wm_invoked = row["Weak Module Invoked"]
                    sym_check = self._get_sym_check_failed(
                        row["Symbols Check"]
                    ).replace("\n", "</br>")
                    supported = row["Driver Flag: Supported"]
                    d_err = self._get_supported_driver_failed(supported)
                    no_err = len(d_err)
                    dv_license = row["Driver Licenses"]
                    lcs_chk = self._fmt_driver_license_check(
                        license, dv_license, vld_lic
                    )
                    lcs_chk.replace("\n", "</br>")
                    if no_err > 0:
                        r.set_attribute("class", "critical_failed_row")
                    if no_err > 1:
                        td(name, rowspan=no_err)
                        td(path, rowspan=no_err)
                        if vendor != "":
                            td(vendor, rowspan=no_err)
                        else:
                            tv = td("no vendor information", rowspan=no_err)
                            tv.set_attribute("class", "important_failed")
                        if signature != "":
                            td(signature, rowspan=no_err)
                        else:
                            ts = td(signature, rowspan=no_err)
                            ts.set_attribute("class", "important_failed")
                        td(distribution, rowspan=no_err)
                        if lcs_chk == "":
                            if license == "":
                                tl = td("No License", rowspan=no_err)
                                tl.set_attribute("class", "important_failed")
                                r.set_attribute("class", "important_failed_row")
                            elif ValidLicense(license, vld_lic):
                                td(license, rowspan=no_err)
                            else:
                                tl = td(license, rowspan=no_err)
                                tl.set_attribute("class", "important_failed")
                                r.set_attribute("class", "important_failed_row")
                        else:
                            tl = td(raw(lcs_chk), rowspan=no_err)
                            tl.set_attribute("class", "important_failed")
                            r.set_attribute("class", "important_failed_row")
                        if wm_invoked or "debuginfo" in name:
                            td(str(wm_invoked), rowspan=no_err)
                        else:
                            tw = td(str(wm_invoked), rowspan=no_err)
                            tw.set_attribute("class", "critical_failed")
                            r.set_attribute("class", "critical_failed_row")
                        t_w = td(d_err[0])
                        t_w.set_attribute("class", "critical_failed")
                        if sym_check == "":
                            t = td("All passed!", rowspan=no_err)
                            t.set_attribute("class", "detail_pass")
                        else:
                            t_w = td(raw(sym_check), rowspan=no_err)
                            t_w.set_attribute("class", "critical_failed")
                            r.set_attribute("class", "critical_failed_row")
                        for val in d_err[1:]:
                            with tr() as r:
                                r.set_attribute("class", "critical_failed_row")
                                t_w = td(val)
                                t_w.set_attribute("class", "critical_failed")
                    else:
                        td(name)
                        td(path)
                        if vendor != "":
                            td(vendor)
                        else:
                            tv = td("no vendor information")
                            tv.set_attribute("class", "important_failed")
                            r.set_attribute("class", "important_failed_row")
                        if signature != "":
                            td(signature)
                        else:
                            ts = td(signature)
                            ts.set_attribute("class", "important_failed")
                        td(distribution)
                        if lcs_chk == "":
                            if license == "":
                                tl = td("No License")
                                tl.set_attribute("class", "important_failed")
                                r.set_attribute("class", "important_failed_row")
                            elif ValidLicense(license, vld_lic):
                                td(license)
                            else:
                                tl = td(license)
                                tl.set_attribute("class", "important_failed")
                                r.set_attribute("class", "important_failed_row")
                        else:
                            tl = td(raw(lcs_chk))
                            tl.set_attribute("class", "important_failed")
                            r.set_attribute("class", "important_failed_row")
                        if wm_invoked or "debuginfo" in name:
                            td(str(wm_invoked))
                        else:
                            tw = td(str(wm_invoked))
                            tw.set_attribute("class", "critical_failed")
                            r.set_attribute("class", "critical_failed_row")
                        if no_err > 0:
                            t_w = td(d_err[0])
                            t_w.set_attribute("class", "critical_failed")
                        else:
                            t = td("All passed!")
                            t.set_attribute("class", "detail_pass")
                        if sym_check == "":
                            t = td("All passed!")
                            t.set_attribute("class", "detail_pass")
                        else:
                            t_w = td(raw(sym_check))
                            t_w.set_attribute("class", "critical_failed")
                            r.set_attribute("class", "critical_failed_row")

        return tb

    def to_html(self, rpm_table, file):
        pkg_path = os.path.dirname(__file__)
        jinja_tmpl = f"{pkg_path}/../config/templates"
        file_loader = FileSystemLoader(jinja_tmpl)
        env = Environment(loader=file_loader)

        rpm_tmpl = env.get_template("rpm-checks.html.jinja")

        rpm_checks = rpm_tmpl.render(
            summary_table=self._get_summary_table_html(rpm_table),
            rpm_details=self._get_table_detail_html(rpm_table),
        )

        with open(file, "w") as f:
            f.write(rpm_checks)

    def to_json(self, rpm_table, file):
        rpm_table.to_json(file, orient="records")

    def _xlsx_create_overview(self, wb):
        et = ExcelTemplate()
        et.set_rpm_check_overview(wb.active)

    def _get_important_failed_style(self):
        (
            ipt_font,
            ipt_border,
            ipt_fill,
        ) = self._style.get_rpm_xslx_table_important_failed()
        return DifferentialStyle(
            font=ipt_font,
            border=ipt_border,
            fill=ipt_fill,
        )

    def _get_critical_failed_style(self):
        (
            ctc_font,
            ctc_border,
            ctc_fill,
        ) = self._style.get_rpm_xslx_table_critical_failed()
        return DifferentialStyle(
            font=ctc_font,
            border=ctc_border,
            fill=ctc_fill,
        )

    def _get_header_style(self):
        (
            header_font,
            header_border,
            header_fill,
        ) = self._style.get_rpm_xslx_table_header()

        return DifferentialStyle(
            font=header_font,
            border=header_border,
            fill=header_fill,
        )

    def _xlsx_create_vendor_summary(self, wb, rpm_table):
        ws_vs = wb.create_sheet("vendor summary")
        sm_table = self._get_summary_table(rpm_table)
        for row in dataframe_to_rows(sm_table, index=False, header=True):
            ws_vs.append(row)

        (
            header_font,
            header_border,
            header_fill,
        ) = self._style.get_rpm_xslx_table_header()

        for cell in ws_vs[1]:
            cell.font = header_font
            cell.border = header_border
            cell.fill = header_fill

        for row in ws_vs[f"A1:G{len(sm_table.index)+1}"]:
            for cell in row:
                cell.border = header_border

        last_record_row_no = len(sm_table.index) + 1
        (
            great_font,
            great_border,
            great_fill,
        ) = self._style.get_rpm_xslx_table_great_row()
        great_row_style = DifferentialStyle(
            font=great_font,
            border=great_border,
            fill=great_fill,
        )
        great_row = Rule(type="expression", dxf=great_row_style)
        great_row.formula = [
            'AND($A2 <> "", VALUE(LEFT($C2, FIND(" ",$C2)-1))=$B2, VALUE(LEFT($D2, FIND(" ", $D2) - 1)) = $B2, VALUE(LEFT($E2, FIND(" ", $E2) - 1)) = $B2, VALUE(LEFT($F2, FIND(" ", $F2)-1))=$B2, VALUE(LEFT($G2, FIND(" ", $G2) - 1))=0)'
        ]
        ws_vs.conditional_formatting.add(f"A2:G{last_record_row_no}", great_row)

        ipt_style = self._get_important_failed_style()
        ctc_style = self._get_critical_failed_style()

        empty_vendor = Rule(type="expression", dxf=ipt_style)
        empty_vendor.formula = ['$A2 = ""']
        ws_vs.conditional_formatting.add(f"A2:A{last_record_row_no}", empty_vendor)

        supported_failed = Rule(type="expression", dxf=ctc_style)
        supported_failed.formula = ['VALUE(LEFT($C2, FIND(" ", $C2) - 1)) <> $B2']
        ws_vs.conditional_formatting.add(f"C2:C{last_record_row_no}", supported_failed)

        license_check = Rule(type="expression", dxf=ipt_style)
        license_check.formula = ['VALUE(LEFT($D2, FIND(" ", $D2) - 1)) <> $B2']
        ws_vs.conditional_formatting.add(f"D2:D{last_record_row_no}", license_check)

        sig_check = Rule(type="expression", dxf=ipt_style)
        sig_check.formula = ['VALUE(LEFT($E2, FIND(" ", $E2) - 1)) <> $B2']
        ws_vs.conditional_formatting.add(f"E2:E{last_record_row_no}", sig_check)

        wm_check = Rule(type="expression", dxf=ipt_style)
        wm_check.formula = ['VALUE(LEFT($F2, FIND(" ", $F2) - 1)) <> $B2']
        ws_vs.conditional_formatting.add(f"F2:F{last_record_row_no}", wm_check)

        sym_failed = Rule(type="expression", dxf=ctc_style)
        sym_failed.formula = ['VALUE(LEFT($G2, FIND(" ", $G2) - 1)) <> 0']
        ws_vs.conditional_formatting.add(f"G2:G{last_record_row_no}", sym_failed)

    def _xlsx_create_rpm_details(self, wb, rpm_table):
        df = self._rename_rpm_detail_columns(rpm_table)
        ws_rd = wb.create_sheet("RPMs details")
        (
            normal_font,
            normal_border,
            normal_fill,
        ) = self._style.get_rpm_xslx_table_normal()
        normal_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        (
            imt_font,
            imt_border,
            imt_fill,
        ) = self._style.get_rpm_xslx_table_important_failed()
        (
            ctc_font,
            ctc_border,
            ctc_fill,
        ) = self._style.get_rpm_xslx_table_critical_failed()
        ctc_style = self._get_critical_failed_style()
        imt_style = self._get_important_failed_style()
        (
            header_font,
            header_border,
            header_fill,
        ) = self._style.get_rpm_xslx_table_header()

        cols = df.columns
        xlsx_cols = list(string.ascii_lowercase[0 : len(cols)])
        for i in range(len(xlsx_cols)):
            cell_no = xlsx_cols[i] + "1"
            ws_rd[cell_no] = cols[i]
            ws_rd[cell_no].font = header_font
            ws_rd[cell_no].fill = header_fill
            ws_rd[cell_no].border = header_border

        ws_rd.column_dimensions["J"].hidden = True

        curr_row_no = 2
        supported_col_no = 0

        for i in range(len(cols)):
            if cols[i] == "Driver Flag: Supported":
                supported_col_no = i
                break

        vld_lic = self._style.get_valid_licenses()

        for i, row in df.iterrows():
            rpm_license = row["License"]
            for col_idx in range(len(cols)):
                cell_no = xlsx_cols[col_idx] + str(curr_row_no)
                val = row[cols[col_idx]]

                ws_rd[cell_no].font = normal_font
                ws_rd[cell_no].fill = normal_fill
                ws_rd[cell_no].border = normal_border
                ws_rd[cell_no].alignment = normal_align

                if cols[col_idx] == "Symbols Check":
                    val = self._get_sym_check_failed(val)
                    if val == "":
                        val = "All passed!"
                        ws_rd[cell_no] = val
                        ws_rd[cell_no].alignment = center_align
                    else:
                        ws_rd[cell_no] = val
                elif cols[col_idx] == "Driver Flag: Supported":
                    val = "All passed!"
                    ws_rd[cell_no] = val
                    ws_rd[cell_no].alignment = center_align
                elif cols[col_idx] == "License":
                    lcs_chk = self._fmt_driver_license_check(
                        rpm_license, row["Driver Licenses"], vld_lic
                    )
                    if lcs_chk == "":
                        if rpm_license == "":
                            ws_rd[cell_no] = "No License"
                            ws_rd[cell_no].font = imt_font
                            ws_rd[cell_no].fill = imt_fill
                            ws_rd[cell_no].border = imt_border
                        else:
                            ws_rd[cell_no] = rpm_license
                    else:
                        ws_rd[cell_no] = lcs_chk
                        ws_rd[cell_no].font = imt_font
                        ws_rd[cell_no].fill = imt_fill
                        ws_rd[cell_no].border = imt_border
                else:
                    ws_rd[cell_no] = str(val)

            failed_drivers = self._get_supported_driver_failed(
                row["Driver Flag: Supported"]
            )
            driver_count = len(failed_drivers)
            if driver_count > 0:  # format supported information
                for sp_idx in range(driver_count):
                    cell_no = xlsx_cols[supported_col_no] + str(curr_row_no + sp_idx)
                    ws_rd[cell_no] = failed_drivers[sp_idx]
                    ws_rd[cell_no].font = ctc_font
                    ws_rd[cell_no].fill = ctc_fill
                    ws_rd[cell_no].border = ctc_border
                    ws_rd[cell_no].alignment = normal_align

            if driver_count > 1:  # need merge cell
                for col_idx in range(len(cols)):
                    if col_idx != supported_col_no:
                        start_cell_no = xlsx_cols[col_idx] + str(curr_row_no)
                        end_cell_no = xlsx_cols[col_idx] + str(
                            curr_row_no + driver_count - 1
                        )
                        merge_range = start_cell_no + ":" + end_cell_no
                        ws_rd.merge_cells(merge_range)

            if driver_count == 0:
                curr_row_no += 1
            else:
                curr_row_no += driver_count

        records = curr_row_no

        empty_vendor = Rule(type="expression", dxf=imt_style)
        empty_vendor.formula = ['$C2 = ""']
        ws_rd.conditional_formatting.add(f"C2:C{records}", empty_vendor)

        sf_rule = Rule(type="expression", dxf=ctc_style)
        sf_rule.formula = [
            '=OR($H2="All passed!", AND(ISNUMBER(FIND(":", $H2)), ISNUMBER(FIND("external", $H2))))'
        ]
        ws_rd.conditional_formatting.add(f"H2:H{records}", sf_rule)

        sig_rule = Rule(type="expression", dxf=ctc_style)
        sig_rule.formula = ['=$D2 <> ""']
        ws_rd.conditional_formatting.add(f"D2:D{records}", sig_rule)

        sym_rule = Rule(type="expression", dxf=ctc_style)
        sym_rule.formula = ['=ISNUMBER(FIND(".ko", $I2))']
        ws_rd.conditional_formatting.add(f"I2:I{records}", sym_rule)

    def _xlsx_create_report_workbook(self):
        wb = Workbook()

        return wb

    def to_excel(self, rpm_table, file):
        if os.path.exists(file):
            os.remove(file)

        wb = self._xlsx_create_report_workbook()

        self._xlsx_create_overview(wb)
        self._xlsx_create_vendor_summary(wb, rpm_table)
        self._xlsx_create_rpm_details(wb, rpm_table)

        wb.save(file)

    def to_pdf(self, rpm_table, file):
        self.to_html(rpm_table, ".tmp.rpms.html")
        pdfkit.from_file(".tmp.rpms.html", file)
        os.remove(".tmp.rpms.html")

    def to_all(self, rpm_table, directory):
        excel_file = os.path.join(directory, "check_result.xlsx")
        html_file = os.path.join(directory, "check_result.html")
        pdf_file = os.path.join(directory, "check_result.pdf")
        json_file = os.path.join(directory, "check_result.json")

        if not os.path.exists(directory):
            os.mkdir(directory)
        else:
            if os.path.exists(excel_file):
                os.remove(excel_file)
            if os.path.exists(html_file):
                os.remove(html_file)
            if os.path.exists(pdf_file):
                os.remove(pdf_file)
            if os.path.exists(json_file):
                os.remove(json_file)

        self.to_excel(rpm_table, excel_file)
        self.to_html(rpm_table, html_file)
        self.to_pdf(rpm_table, pdf_file)
        self.to_json(rpm_table, json_file)


class DriversExporter:
    def __init__(self, logger):
        self._logger = logger
        self._style = SDCConf()

    def _driver_path_check(self, driver_path):
        # TODO: this should be optimized!
        result = re.match(
            r"^/lib/modules/[0-9]+.[0-9]+.[0-9]+\-[0-9]+\-[a-z]+/(updates/|weak-updates/|extra/)",
            driver_path,
        )

        if result is not None:
            return result
        else:
            return re.match(
                r"^/lib/modules/[0-9]+.[0-9]+.[0-9]+\-[0-9]+.[0-9]+\-[a-z]+/(updates/|weak-updates/|extra/)",
                driver_path,
            )

    def _format_row_html(self, row):
        path = row["path"]
        supported = row["flag_supported"]
        supported = supported.split(" ")
        license = row["license"]
        signature = row["signature"]
        rpm = row["rpm"]
        vld_lic = self._style.get_valid_licenses()

        critical_style = self._style.get_driver_html_warn_critical()
        important_style = self._style.get_driver_html_warn_important()
        cs_bgColor = critical_style["background-color"]
        cs_color = critical_style["color"]
        cs_border = critical_style["border"]

        is_bgColor = important_style["background-color"]
        is_border = important_style["border"]

        warn_level = 0  # 0: normal, 1: important, 2: critical

        name_style = ""
        path_style = ""
        supported_style = ""
        license_style = ""
        signature_style = ""
        suse_release_style = ""
        running_style = ""
        rpm_style = ""

        if not ValidLicense(license, vld_lic):
            warn_level = 1
            license_style = f"background-color:{is_bgColor}"

        if not signature:
            warn_level = 1
            signature_style = f"background-color:{is_bgColor}"

        if not self._driver_path_check(path):
            warn_level = 2
            path_style = f"background-color:{cs_bgColor} color:{cs_color}"

        if (len(supported) == 0) or (
            len(supported) == 1 and supported[0] != "external"
        ):
            warn_level = 2
            supported_style = f"background-color:{cs_bgColor} color:{cs_color}"
        if len(supported) > 1:
            v1 = supported[0]
            if v1 != "external":
                warn_level = 2
                supported_style = f"background-color:{cs_bgColor} color:{cs_color}"
            else:
                warn_level = 1
                supported_style = f"background-color:{is_bgColor}"
                for v in supported:
                    if v != v1 and v != "external":
                        warn_level = 2
                        supported_style = (
                            f"background-color:{cs_bgColor} color:{cs_color}"
                        )

        if "is not owned by any package" in rpm:
            warn_level = 2
            rpm_style = f"background-color:{cs_bgColor} color:{cs_color}"

        row_style = [
            name_style,
            path_style,
            supported_style,
            license_style,
            signature_style,
            suse_release_style,
            running_style,
            rpm_style,
        ]
        return row_style

    def to_json(self, driver_tables, file):
        jf = dict()
        for label, driver_table in driver_tables.items():
            if driver_table is not None:
                buff = driver_table.to_json(orient="records")
            else:
                buff = "{}"
            jf[label] = json.loads(buff)

        with open(file, "w") as fp:
            json.dump(jf, fp)

    def _get_third_party_drivers(self, drivers):
        df = drivers.copy()
        sig_keys = self._style.get_driver_sig_keys()
        keys = []
        for k in sig_keys:
            keys.append(k["key"])

        ser = ~df.rpm_sig_key.isin(keys)
        df = df[ser]
        df.drop("rpm_sig_key", axis=1, inplace=True)

        return df

    def _refmt_supported(self, drivers):
        df = drivers.copy()
        for i, row in df.iterrows():
            row["flag_supported"] = " ".join(row["flag_supported"])

        return df

    def to_html(self, driver_tables, file):
        pkg_path = os.path.dirname(__file__)
        jinja_tmpl = f"{pkg_path}/../config/templates"
        file_loader = FileSystemLoader(jinja_tmpl)
        env = Environment(loader=file_loader)

        driver_tmpl = env.get_template("driver-checks.html.jinja")

        details = []
        for label, dt in driver_tables.items():
            if dt is None:
                details.append({"name": label, "table": "Connect error!"})
                continue

            total_drivers, tp_drivers, failed_drivers = self._get_server_summary(dt)
            df = dt.copy()
            df = self._get_third_party_drivers(df)
            df.loc[df["running"] == "True", "running"] = "&#9989;"
            df.loc[df["running"] == "False", "running"] = "&#9940;"
            df = self._refmt_supported(df)
            ts = (
                df.style.hide_index()
                .set_table_attributes('class="table_center"')
                .apply(self._format_row_html, axis=1)
            )

            details.append(
                {
                    "name": label,
                    "total_drivers": total_drivers,
                    "third_party_drivers": tp_drivers,
                    "failed_drivers": failed_drivers,
                    "table": ts.render(),
                }
            )

        driver_checks = driver_tmpl.render(details=details)

        with open(file, "w") as f:
            f.write(driver_checks)

    def _xlsx_create_overview(self, wb):
        et = ExcelTemplate()
        et.set_driver_check_overview(wb.active)

    def _get_failed_driver_count(self, df):
        count = 0
        vld_lic = self._style.get_valid_licenses()
        for i, row in df.iterrows():
            if (
                "is not owned by any package" in row["rpm"]
                or row["flag_supported"] != "external"
                or row["signature"] == ""
                or self._driver_path_check(row["path"]) is None
            ):
                count += 1
                continue

        return count

    def _get_server_summary(self, driver_table):
        total_drivers = len(driver_table.index)
        third_party_drivers = self._get_third_party_drivers(driver_table)
        tpd_count = len(third_party_drivers.index)

        failed_count = self._get_failed_driver_count(third_party_drivers)

        return total_drivers, tpd_count, failed_count

    def _xlsx_create_table(self, wb, label, driver_table):
        ws_dc = wb.create_sheet(label)
        if driver_table is None:
            return

        df = self._get_third_party_drivers(driver_table)
        df = self._refmt_supported(df)
        for row in dataframe_to_rows(df, index=False, header=True):
            ws_dc.append(row)

        (
            header_font,
            header_border,
            header_fill,
        ) = self._style.get_driver_xslx_table_header()
        for cell in ws_dc[1]:
            cell.font = header_font
            cell.border = header_border
            cell.fill = header_fill

        (
            ctc_font,
            ctc_border,
            ctc_fill,
        ) = self._style.get_driver_xslx_table_critical_failed()
        (
            imt_font,
            imt_border,
            imt_fill,
        ) = self._style.get_driver_xslx_table_important_failed()
        (
            normal_font,
            normal_border,
            normal_fill,
        ) = self._style.get_driver_xslx_table_normal()
        vld_lic = self._style.get_valid_licenses()

        last_record_row_no = len(df.index) + 2  # the title of the table also count
        for i in range(2, last_record_row_no):
            # default format.
            for cell in ws_dc[i]:
                cell.font = normal_font
                cell.border = normal_border
                cell.fill = normal_fill

            path = ws_dc[f"B{i}"].value
            flag = ws_dc[f"C{i}"].value.split(" ")
            license = ws_dc[f"D{i}"].value
            sig = ws_dc[f"E{i}"].value
            rpm = ws_dc[f"H{i}"].value

            w_level = 0

            if not ValidLicense(license, vld_lic):
                w_level = 1
                ws_dc[f"D{i}"].font = imt_font
                ws_dc[f"D{i}"].border = imt_border
                ws_dc[f"D{i}"].fill = imt_fill

            if sig == "":
                w_level = 1
                ws_dc[f"E{i}"].font = imt_font
                ws_dc[f"E{i}"].border = imt_border
                ws_dc[f"E{i}"].fill = imt_fill

            if not self._driver_path_check(path):
                w_level = 2
                ws_dc[f"B{i}"].font = imt_font
                ws_dc[f"B{i}"].border = imt_border
                ws_dc[f"B{i}"].fill = imt_fill

            if (len(flag) == 0) or (len(flag) == 1 and flag[0] != "external"):
                w_level = 2
                ws_dc[f"C{i}"].font = ctc_font
                ws_dc[f"C{i}"].border = ctc_border
                ws_dc[f"C{i}"].fill = ctc_fill
            elif len(flag) > 1:
                v1 = flag[0]
                if v1 != "external":
                    warn_level = 2
                    ws_dc[f"C{i}"].font = ctc_font
                    ws_dc[f"C{i}"].border = ctc_border
                    ws_dc[f"C{i}"].fill = ctc_fill
                else:
                    warn_level = 1
                    ws_dc[f"C{i}"].font = imt_font
                    ws_dc[f"C{i}"].border = imt_border
                    ws_dc[f"C{i}"].fill = imt_fill
                    for v in flag:
                        if v != v1:
                            warn_level = 2
                            ws_dc[f"C{i}"].font = ctc_font
                            ws_dc[f"C{i}"].border = ctc_border
                            ws_dc[f"C{i}"].fill = ctc_fill
                            break

            if "is not owned by any package" in rpm:
                warn_level = 2
                ws_dc[f"H{i}"].font = ctc_font
                ws_dc[f"H{i}"].border = ctc_border
                ws_dc[f"H{i}"].fill = ctc_fill

    def to_excel(self, driver_tables, file):
        wb = Workbook()
        self._xlsx_create_overview(wb)

        for label, dt in driver_tables.items():
            self._xlsx_create_table(wb, label, dt)

        if os.path.exists(file):
            os.remove(file)

        wb.save(file)

    def to_pdf(self, driver_tables, file):
        self.to_html(driver_tables, ".tmp.rpms.html")

        content = ""
        with open(".tmp.rpms.html", "r") as fp:
            content = fp.read()

        content = str(content).replace("&#9989;", "True").replace("&#9940;", "False")
        with open(".tmp.rpms.html", "w") as fp:
            fp.write(content)

        pdfkit.from_file(".tmp.rpms.html", file)
        os.remove(".tmp.rpms.html")

    def to_all(self, driver_tables, directory):
        excel_file = os.path.join(directory, "check_result.xlsx")
        html_file = os.path.join(directory, "check_result.html")
        pdf_file = os.path.join(directory, "check_result.pdf")
        json_file = os.path.join(directory, "check_result.json")

        if not os.path.exists(directory):
            os.mkdir(directory)
        else:
            if os.path.exists(excel_file):
                os.remove(excel_file)
            if os.path.exists(html_file):
                os.remove(html_file)
            if os.path.exists(pdf_file):
                os.remove(pdf_file)
            if os.path.exists(json_file):
                os.remove(json_file)

        self.to_excel(driver_tables, excel_file)
        self.to_html(driver_tables, html_file)
        self.to_pdf(driver_tables, pdf_file)
        self.to_pdf(driver_tables, json_file)
