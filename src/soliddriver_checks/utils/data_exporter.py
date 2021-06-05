from numpy import c_
from numpy.core.fromnumeric import shape
import pdfkit
import pandas as pd
import os
from pathlib import Path
import dominate
from dominate.tags import html, body, h1, div, tr, td, th, table, style, ul, li, p
from dominate.util import raw
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment, NamedStyle
from openpyxl.styles.differential import DifferentialStyle
from openpyxl import load_workbook
from openpyxl.formatting.rule import Rule
from openpyxl.utils.dataframe import dataframe_to_rows
import json
import ast
import string
from openpyxl import Workbook
import time


class StyleConfig:
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
        )
        sd = Side(
            border_style=conf["side"]["border_style"], color=conf["side"]["color"]
        )
        bd = Border(top=sd, left=sd, right=sd, bottom=sd)
        fill = PatternFill(start_color=conf["fill"]["bgcolor"],
                           end_color=conf["fill"]["bgcolor"],
                           fill_type="solid")

        return font, bd, fill

    def get_rpm_html_css(self):
        return self._conf["rpm-check"]["html"]

    def get_rpm_xslx_table_header(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "header")

    def get_rpm_xslx_table_normal(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "data", "normal")

    def get_rpm_xslx_table_warning(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "data", "warning")

    def get_rpm_xslx_table_great_row(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "row", "great")

    def get_rpm_xslx_table_warn_row(self):
        return self._get_xlsx_info("rpm-check", "excel", "table", "row", "warn")

    def get_driver_html_css(self):
        return self._conf["driver-check"]["html"]["style"]

    def get_driver_html_warning_data(self):
        return self._conf["driver-check"]["html"]["data"]["warn"]["bgcolor"]

    def get_driver_html_warning_row(self):
        return self._conf["driver-check"]["html"]["row"]["warn"]["border"]

    def get_driver_xslx_table_header(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "header")

    def get_driver_xslx_table_normal(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "data", "normal")

    def get_driver_xslx_table_warning(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "data", "warning")

    def get_driver_xslx_table_warn_row(self):
        return self._get_xlsx_info("driver-check", "excel", "table", "row", "warn")

class RPMsExporter:
    def __init__(self, logger):
        self._logger = logger
        self._style = StyleConfig()

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
        df = df.rename(
            columns={
                "Driver Flag: supported": "supported",
                "Symbols Check": "symbols_check",
            }
        )
        df["supported"] = df["supported"].astype(str)
        df["symbols_check"] = df["symbols_check"].astype(str)
        df.loc[df["supported"].str.contains("Missing"), "supported"] = "Missing"
        df.loc[df["supported"].str.contains("yes"), "supported"] = "yes"
        df.loc[df["supported"].str.contains("external"), "supported"] = "external"
        df.loc[df["supported"] == "", "supported"] = "no drivers"

        df.loc[df["symbols_check"].str.contains("ko"), "symbols_check"] = "failed"
        df.loc[df["symbols_check"] == "{}", "symbols_check"] = "pass"

        vendors = df["Vendor"].unique()
        df_summary = pd.DataFrame(
            columns=[
                "vendor",
                "total rpms",
                "supported:yes",
                "supported:external",
                "no supported flag",
                "symbols check failed",
                "symbols check pass",
            ]
        )
        for v in vendors:
            df_vendor = df.loc[df["Vendor"] == v]
            total = len(df_vendor.index)
            missing = len(
                df_vendor.loc[
                    df_vendor["supported"].str.contains("Missing"), "supported"
                ].index
            )
            yes = len(
                df_vendor.loc[
                    df_vendor["supported"].str.contains("yes"), "supported"
                ].index
            )
            external = len(
                df_vendor.loc[
                    ~df_vendor["supported"].str.contains("yes")
                    & ~df_vendor["supported"].str.contains("Missing"),
                    "supported",
                ].index
            )
            failed = len(
                df_vendor.loc[
                    df_vendor["symbols_check"] == "failed", "symbols_check"
                ].index
            )
            pass_ = total - failed
            df_summary = df_summary.append(
                {
                    "vendor": v,
                    "total rpms": total,
                    "supported:yes": f"{yes} ({yes/total * 100:.2f})",
                    "supported:external": f"{external} ({external/total * 100:.2f}%)",
                    "no supported flag": f"{missing} ({missing/total * 100:.2f}%)",
                    "symbols check failed": f"{failed} ({failed/total * 100:.2f}%)",
                    "symbols check pass": f"{pass_} ({pass_/total * 100:.2f}%)",
                },
                ignore_index=True,
            )

        return df_summary

    def to_html(self, rpm_table, file):
        report = dominate.document(title="checking result from soliddriver-checks")

        with report:
            with report.head:
                style(self._style.get_rpm_html_css())
            with div():
                title = h1("Solid driver check result (RPMs)")
                title.set_attribute(
                    "style",
                    "text-align: center; font-size:x-large;background-color: #30BA78;",
                )
            context = p(
                "soliddriver-checks is a tool for parnter(s) and customer(s) to check their RPMs to ensure these are meet basic SUSE requirements."
            )
            context.set_attribute("style", "font-size:small;")
            context = p(
                raw(
                    'Please refer to <a href="https://drivers.suse.com/doc/kmpm/" style="background-color: #30BA78;">Kernel Module Packages Manual</a> to learn how to build a KMP(Kernel Module Package).'
                )
            )
            context.set_attribute("style", "font-size:x-small")
            context = p("What do we check?")
            with ul() as u:
                u.set_attribute("style", "font-size:x-small")
                li(
                    "supported flag: 'yes' means this package is built by SUSE and supported by SUSE, 'external' means this package is built by vendor and supported by both SUSE and vendor, 'Missing' or others means this package does not contain 'supported' flag or unrecognizable 'supported' flag, please contact your IHV or who provide this package to you, we don't recommend you install it. "
                )
                li(
                    "symbol check: For all KMP packages, the symbols needed by the drivers in this packages, should also have the requires in RPM and the checksum should match. Otherwise we don't recommend you install it."
                )
                li(
                    "signature: We list it here but not check if it's from the vendor in the list, please veirfy it by youself."
                )
                li(
                    "vendor: SUSE partner who provides and supports the kernel module code and packaging."
                )

            with div():
                summary_title = p("Summary of the result from vendor perspective: ")
                summary_title.set_attribute(
                    "style",
                    "text-align: center; font-size:large;background-color: #30BA78;",
                )

            with table() as tb:
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
                        vendor = row["vendor"]
                        total_rpms = row["total rpms"]
                        s_yes = row["supported:yes"]
                        s_external = row["supported:external"]
                        s_missing = row["no supported flag"]
                        sym_pass = row["symbols check pass"]
                        sym_failed = row["symbols check failed"]

                        row_passed = False
                        if (
                            int(s_external.split(" ")[0]) == total_rpms
                            and int(sym_pass.split(" ")[0]) == total_rpms
                        ):
                            row_passed = True
                        with tr() as r:
                            if row_passed:
                                r.set_attribute("class", "summary_row_great")
                            if vendor != "":
                                td(vendor)
                            else:
                                tv = td("no vendor information")
                                tv.set_attribute("class", "item_check_failed")
                            with td(total_rpms) as t:
                                t.set_attribute("class", "summary_total")
                            with td(s_yes) as t:
                                if int(s_yes.split(" ")[0]) != 0:
                                    t.set_attribute(
                                        "class", "item_check_failed summary_number"
                                    )
                                else:
                                    t.set_attribute("class", "summary_number")
                            with td(s_external) as t:
                                t.set_attribute("class", "summary_number")
                            with td(s_missing) as t:
                                if int(s_missing.split(" ")[0]) != 0:
                                    t.set_attribute(
                                        "class", "item_check_failed summary_number"
                                    )
                                else:
                                    t.set_attribute("class", "summary_number")
                            with td(sym_failed) as t:
                                if int(sym_failed.split(" ")[0]) != 0:
                                    t.set_attribute(
                                        "class", "item_check_failed summary_number"
                                    )
                                else:
                                    t.set_attribute("class", "summary_number")
                            with td(sym_pass) as t:
                                t.set_attribute("class", "summary_number")

            with div():
                detail_table = p("Check result in details: ")
                detail_table.set_attribute(
                    "style",
                    "text-align: center; font-size:large;background-color: #30BA78;",
                )

            with table() as tb:
                tb.set_attribute("class", "table_center")
                with tr():
                    cols = rpm_table.columns
                    for col in cols:
                        if col == "Path":
                            tp = th(col)
                            tp.set_attribute("class", "detail_path")
                        else:
                            th(col)

                for i, row in rpm_table.iterrows():
                    supported = row["Driver Flag: supported"]
                    d_err = self._get_supported_driver_failed(supported)
                    no_err = len(d_err)
                    with tr() as r:
                        if no_err > 0:
                            r.set_attribute("class", "warning_row_border")
                        name = row["Name"]
                        path = row["Path"]
                        vendor = row["Vendor"]
                        signature = row["Signature"]
                        distribution = row["Distribution"]
                        sym_check = self._get_sym_check_failed(
                            row["Symbols Check"]
                        ).replace("\n", "</br>")
                        if no_err > 1:
                            td(name, rowspan=no_err)
                            td(path, rowspan=no_err)
                            if vendor != "":
                                td(vendor, rowspan=no_err)
                            else:
                                tv = td("no vendor information", rowspan=no_err)
                                tv.set_attribute("class", "detail_no_vendor")
                                r.set_attribute("class", "warning_row_border")
                            td(signature, rowspan=no_err)
                            td(distribution, rowspan=no_err)
                            t_w = td(d_err[0])
                            t_w.set_attribute("class", "supported_failed")
                            if sym_check == "":
                                t = td("All passed!", rowspan=no_err)
                                t.set_attribute("class", "detail_pass")
                            else:
                                t_w = td(raw(sym_check), rowspan=no_err)
                                t_w.set_attribute("class", "sym_check_failed")
                                r.set_attribute("class", "warning_row_border")
                            for val in d_err[1:]:
                                with tr() as r:
                                    r.set_attribute("class", "warning_row_border")
                                    t_w = td(val)
                                    t_w.set_attribute("class", "supported_failed")
                        else:
                            td(name)
                            td(path)
                            if vendor != "":
                                td(vendor)
                            else:
                                tv = td("no vendor information")
                                tv.set_attribute("class", "detail_no_vendor")
                                r.set_attribute("class", "warning_row_border")
                            td(signature)
                            td(distribution)
                            if no_err > 0:
                                t_w = td(d_err[0])
                                t_w.set_attribute("class", "supported_failed")
                            else:
                                t = td("All passed!")
                                t.set_attribute("class", "detail_pass")
                            if sym_check == "":
                                t = td("All passed!")
                                t.set_attribute("class", "detail_pass")
                            else:
                                t_w = td(raw(sym_check))
                                t_w.set_attribute("class", "sym_check_failed")
                                r.set_attribute("class", "warning_row_border")

        with open(file, "w") as f:
            f.write(report.render())

    def to_json(self, rpm_table, file):
        rpm_table.to_json(file, orient="records")

    def _xlsx_create_overview(self, wb):
        ws_ov = wb.active
        ws_ov.title = "overview"

        c_name = "A1"
        ft_name = "Poppins Medium"
        ws_ov[c_name] = "Solid driver check result(RPMs)"
        ws_ov[c_name].alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=False
        )
        ws_ov[c_name].fill = PatternFill(start_color="30BA78", end_color="30BA78", fill_type="solid")
        ws_ov[c_name].font = Font(name=ft_name, size=18, bold=True)
        ws_ov.merge_cells("A1:J1")

        c_name = "A3"
        ws_ov[
            c_name
        ] = "soliddriver-checks is a tool for parnter(s) and customer(s) to check their RPMs to ensure these are meet basic SUSE requirements."
        ws_ov[c_name].font = Font(name=ft_name, size=11)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov.merge_cells("A3:J3")

        c_name = "A5"
        ws_ov[
            c_name
        ] = "Please refer to Kernel Module Packages Manual to learn how to build a KMP(Kernel Module Package)."
        ws_ov[c_name].font = Font(name=ft_name, size=8)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov.merge_cells("A5:J5")

        c_name = "A7"
        ws_ov[c_name] = "What do we check?"
        ws_ov[c_name].font = Font(name=ft_name, size=14)
        ws_ov.merge_cells("A7:J7")

        sd = Side(border_style="thin", color="30BA78")
        bd = Border(top=sd, left=sd, right=sd, bottom=sd)
        c_name = "A8"
        ws_ov[
            c_name
        ] = "supported flag: 'yes' means this package is built by SUSE and supported by SUSE, 'external' means this package is built by vendor and supported by both SUSE and vendor, 'Missing' or others means this package does not contain 'supported' flag or unrecognizable 'supported' flag, please contact your IHV or who provide this package to you, we don't recommend you install it."
        ws_ov[c_name].font = Font(name=ft_name, size=8)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov[c_name].border = bd
        ws_ov.merge_cells("A8:J8")

        c_name = "A9"
        ws_ov[
            c_name
        ] = "symbol check: For all KMP packages, the symbols needed by the drivers in this packages, should also have the requires in RPM and the checksum should match. Otherwise we don't recommend you install it."
        ws_ov[c_name].font = Font(name=ft_name, size=8)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov[c_name].border = bd
        ws_ov.merge_cells("A9:J9")

        c_name = "A10"
        ws_ov[
            c_name
        ] = "signature: We list it here but not check if it's from the vendor in the list, please veirfy it by youself."
        ws_ov[c_name].font = Font(name=ft_name, size=8)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov[c_name].border = bd
        ws_ov.merge_cells("A10:J10")

        c_name = "A11"
        ws_ov[
            c_name
        ] = "vendor: SUSE partner who provides and supports the kernel module code and packaging."
        ws_ov[c_name].font = Font(name=ft_name, size=8)
        ws_ov[c_name].alignment = Alignment(wrap_text=True)
        ws_ov[c_name].border = bd
        ws_ov.merge_cells("A11:J11")

    def _xlsx_create_vendor_summary(self, wb, rpm_table):
        ws_vs = wb.create_sheet("vendor summary")
        sm_table = self._get_summary_table(rpm_table)
        for row in dataframe_to_rows(sm_table, index=False, header=True):
            ws_vs.append(row)

        header_font, header_border, header_fill = self._style.get_rpm_xslx_table_header()
        for cell in ws_vs[1]:
            cell.font = header_font
            cell.border = header_border
            cell.fill = header_fill

        for row in ws_vs[f"A1:G{len(sm_table.index)+1}"]:
            for cell in row:
                cell.border = header_border

        last_record_row_no = len(sm_table.index) + 1
        great_font, great_border, great_fill = self._style.get_rpm_xslx_table_great_row()
        great_row_style = DifferentialStyle(
            font=great_font,
            border=great_border,
            fill=great_fill,
        )
        great_row = Rule(type="expression", dxf=great_row_style)
        great_row.formula = [
            'AND(VALUE(LEFT($D2, FIND(" ",$D2)-1)) = $B2, VALUE(LEFT($G2, FIND(" ", $G2)-1)) = $B2)'
        ]
        ws_vs.conditional_formatting.add(f"A2:G{last_record_row_no}", great_row)

        warn_font, warn_border, warn_fill = self._style.get_rpm_xslx_table_warning()
        warning_style = DifferentialStyle(
            font=warn_font,
            border=warn_border,
            fill=warn_fill,
        )
        empty_vendor = Rule(type="expression", dxf=warning_style)
        empty_vendor.formula = ['$A2 = ""']
        ws_vs.conditional_formatting.add(f"A2:A{last_record_row_no}", empty_vendor)

        supported_yes = Rule(type="expression", dxf=warning_style)
        supported_yes.formula = ['VALUE(LEFT($C2, FIND(" ", $C2) - 1)) <> 0']
        ws_vs.conditional_formatting.add(f"C2:C{last_record_row_no}", supported_yes)

        supported_missing = Rule(type="expression", dxf=warning_style)
        supported_missing.formula = ['VALUE(LEFT($E2, FIND(" ", $E2) - 1)) <> 0']
        ws_vs.conditional_formatting.add(f"E2:E{last_record_row_no}", supported_missing)

        sym_failed = Rule(type="expression", dxf=warning_style)
        sym_failed.formula = ['VALUE(LEFT($F2, FIND(" ", $F2) - 1)) <> 0']
        ws_vs.conditional_formatting.add(f"F2:F{last_record_row_no}", sym_failed)

    def _xlsx_create_rpm_details(self, wb, rpm_table):
        ws_rd = wb.create_sheet("RPMs details")
        normal_font, normal_border, normal_fill = self._style.get_rpm_xslx_table_normal()
        normal_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        warn_font, warn_border, warn_fill = self._style.get_rpm_xslx_table_warning()
        header_font, header_border, header_fill = self._style.get_rpm_xslx_table_header()

        cols = rpm_table.columns
        xlsx_cols = list(string.ascii_lowercase[0:len(cols)])
        for i in range(len(xlsx_cols)):
            cell_no = xlsx_cols[i] + "1"
            ws_rd[cell_no] = cols[i]
            ws_rd[cell_no].font = header_font
            ws_rd[cell_no].fill = header_fill
            ws_rd[cell_no].border = header_border

        curr_row_no = 2
        supported_col_no = 0

        for i in range(len(cols)):
            if cols[i] == "Driver Flag: supported":
                supported_col_no = i
                break

        for i, row in rpm_table.iterrows():
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
                        ws_rd[cell_no].alignment = center_align
                elif cols[col_idx] == "Driver Flag: supported":
                    val = "All passed!"
                    ws_rd[cell_no].alignment = center_align
                ws_rd[cell_no] = val

            failed_drivers = self._get_supported_driver_failed(
                row["Driver Flag: supported"]
            )
            driver_count = len(failed_drivers)
            if driver_count > 0:  # format supported information
                for sp_idx in range(driver_count):
                    cell_no = xlsx_cols[supported_col_no] + str(curr_row_no + sp_idx)
                    ws_rd[cell_no] = failed_drivers[sp_idx]
                    ws_rd[cell_no].font = warn_font
                    ws_rd[cell_no].fill = warn_fill
                    ws_rd[cell_no].border = warn_border
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
        support_area = "F2:F" + str(records)
        ds_warn = DifferentialStyle(font=warn_font, border=warn_border, fill=warn_fill)

        support_flag_na_rule = Rule(
            type="containsText", operator="containsText", text="Missing", dxf=ds_warn
        )
        support_flag_yes_rule = Rule(
            type="containsText", operator="containsText", text="yes", dxf=ds_warn
        )

        ws_rd.conditional_formatting.add(support_area, support_flag_na_rule)
        ws_rd.conditional_formatting.add(support_area, support_flag_yes_rule)

        sym_area = "G2:G" + str(records)
        mismatch_rule = Rule(
            type="containsText", operator="containsText", text=".ko", dxf=ds_warn
        )

        ws_rd.conditional_formatting.add(sym_area, mismatch_rule)

        empty_vendor =Rule(type="expression", dxf=ds_warn)
        empty_vendor.formula = ['$C2 = ""']
        ws_rd.conditional_formatting.add(f"C2:C{records}", empty_vendor)

        warn_row_style = DifferentialStyle(
            border=warn_border
        )
        warn_row = Rule(type="expression", dxf=warn_row_style)
        warn_row.formula = [
            'OR($F2 <> "All passed!", $G2 <> "All passed!", $C2 = "")'
        ]
        ws_rd.conditional_formatting.add(f"A2:G{records}", warn_row)

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
        self._style = StyleConfig()

    def _fmt_rpm_info(self, val):
        color = self._style.get_driver_html_warning_data()
        if "is not owned by any package" in val:
            return "background-color:%s;" % color
        else:
            return ""

    def _fmt_supported_flag(self, val):
        color = self._style.get_driver_html_warning_data()
        if val != "external" and val != "yes":
            return "background-color:%s;" % color
        else:
            return ""

    def _fmt_warning_row_border(self, row):
        border = self._style.get_driver_html_warning_row()
        return [f"border:{border}" if (row["Flag: supported"] != "external" and row["Flag: supported"] != "yes") or "is not owned by any package" in row["RPM Information"] else "" for r in row]

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

    def to_html(self, driver_tables, file):
        report = dominate.document(title="checking result from soliddriver-checks")

        with report:
            with report.head:
                style(self._style.get_driver_html_css())
            with body():
                for label, dt in driver_tables.items():
                    df = dt.copy()
                    df.loc[df["Running"] == "True", "Running"] = "&#9989;"
                    df.loc[df["Running"] == "False", "Running"] = "&#9940;"
                    ts = df.style.hide_index()\
                           .set_table_attributes('class="table_center"')\
                           .applymap(self._fmt_rpm_info, subset=pd.IndexSlice[:, ["RPM Information"]])\
                           .applymap(self._fmt_supported_flag, subset=pd.IndexSlice[:, ["Flag: supported"]])\
                           .apply(self._fmt_warning_row_border, axis=1)

                    with div():
                        detail_table = p('Solid Driver Checking Result: %s' % label)
                        detail_table.set_attribute(
                                        "style",
                                        "text-align: center; font-size:large;background-color: #30BA78;",
                                        )

                    raw(ts.render())

        with open(file, "w") as f:
            f.write(report.render())

    def _xlsx_create_overview(self, wb):
        pass

    def _xlsx_create_table(self, wb, label, driver_table):
        ws_dc = wb.create_sheet(label)
        for row in dataframe_to_rows(driver_table, index=False, header=True):
            ws_dc.append(row)

        header_font, header_border, header_fill = self._style.get_driver_xslx_table_header()
        for cell in ws_dc[1]:
            cell.font = header_font
            cell.border = header_border
            cell.fill = header_fill

        for row in ws_dc[f"A1:F{len(driver_table.index)+1}"]:
            for cell in row:
                cell.border = header_border

        last_record_row_no = len(driver_table.index) + 1

        warn_font, warn_border, warn_fill = self._style.get_driver_xslx_table_warning()
        warning_style = DifferentialStyle(
            font=warn_font,
            border=warn_border,
            fill=warn_fill,
        )
        sup_failed = Rule(type="expression", dxf=warning_style)
        sup_failed.formula = ['AND($C2 <> "external", $C2 <> "yes")']
        ws_dc.conditional_formatting.add(f"C2:C{last_record_row_no}", sup_failed)

        rpm_failed = Rule(type="expression", dxf=warning_style)
        rpm_failed.formula = ['ISNUMBER(SEARCH("is not owned by any package", $F2))']
        ws_dc.conditional_formatting.add(f"F2:F{last_record_row_no}", rpm_failed)

        warn_row_style = DifferentialStyle(
            border=warn_border
        )
        warn_row = Rule(type="expression", dxf=warn_row_style)
        warn_row.formula = [
            'OR(AND($C2 <> "external", $C2 <> "yes"), ISNUMBER(SEARCH("is not owned by any package", $F2)))'
        ]
        ws_dc.conditional_formatting.add(f"A2:F{last_record_row_no}", warn_row)

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
