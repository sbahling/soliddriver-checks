import pdfkit
import pandas as pd
import os
import dominate
from dominate.tags import html, body, h1, div, tr, td, table
from dominate.util import raw
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.styles.borders import Border, Side
from openpyxl.styles.differential import DifferentialStyle
from openpyxl import load_workbook
from openpyxl.formatting.rule import Rule
import json
import ast
import string
from openpyxl import Workbook
import time
# import importlib_resources
# import pkgutil


class FormatConfig:
    def __init__(self):
        pkg_path = os.path.dirname(__file__)
        cfg_path = f"{pkg_path}/../config/soliddriver-checks.conf"

        with open(cfg_path, 'r') as fp:
            self._formatting = json.load(fp)

    def load_body_format(self):
        return self._formatting["body"]

    def load_table_format(self):
        return self._formatting["table"]

    def load_rpm_info_format(self):
        return self._formatting['highlight']['rpm-info']

    def load_support_flag_format(self):
        return self._formatting['highlight']['support-flag']

    def load_running_format(self):
        return self._formatting['highlight']['running']
    
    def load_symbol_format(self):
        return self._formatting['highlight']['symbol']


class HTMLTableFormatting:
    def __init__(self):
        self._formatting = FormatConfig()

    def get_style(self):
        table_formatting = self._formatting.load_table_format()
        styles = [
            dict(selector='table',
                 props=[('border', table_formatting['border'])]),
            dict(selector='th',
                 props=[('border', table_formatting['th']['border']),
                        ('font-size', table_formatting['th']['font-size']),
                        ('font-family', table_formatting['th']['font-family']),
                        ('background-color',
                        table_formatting['th']['background-color'])]),
            dict(selector='td',
                 props=[('border', table_formatting['th']['border']),
                        ('font-size', table_formatting['td']['font-size']),
                        ('font-family',
                        table_formatting['td']['font-family'])])
            ]

        return styles


class RPMsExporter:
    def __init__(self, logger):
        self._logger = logger
        self._formatting = FormatConfig()

    def _supported_render(self, value):
        formatting = self._formatting.load_support_flag_format()
        bgcolor_missing = formatting['Missing']['background-color']
        bgcolor_yes = formatting['yes']['background-color']
        # bgcolor_external = formatting['external']['background-color']
        if ': no' in value or ': Missing' in value:
            return 'background-color: ' + bgcolor_missing
        elif ': yes' in value:
            return 'background-color: ' + bgcolor_yes
        # elif ': external' in value:
        #     return 'background-color: ' + bgcolor_external
        else:
            return 'background-color: white'

    def _symbol_render(self, value):
        if value == '':
            return ''

        formatting = self._formatting.load_symbol_format()
        bgcolor = formatting['mismatch']['background-color']
        return 'background-color: %s' % bgcolor


    def _highlight_supported_error(self, row):
        return ['background-color: #CD5C5C; color: white' if row[1] != 'external' else '' for r in row]

    def _fmt_supported_to_html(self, val):
        if val == '':
            return ''
        else:
            val = ast.literal_eval(val)
            df = pd.DataFrame.from_dict(val, orient='index')
            s = df.style.apply(self._highlight_supported_error, axis=1).\
                hide_index()
            return s.render(head=[])

    def _fmt_driver_symbol_result(self, val):
        unfound = ""
        for i in range(len(val['unfound'])):
            if i % 5 == 0:
                unfound += "\n"
            unfound += val['unfound'][i] + ", "

        mismatch = ""
        for i in range(len(val['checksum-mismatch'])):
            if i % 5 == 0:
                mismatch += "\n"
            mismatch += val['checksum-mismatch'][i] + ", "

        return "Can't find symbols in RPM: \n" + unfound + "\n\n" + "symbols check sum doesn't match in RPM: \n" + mismatch

    def _fmt_symbol_check_to_html(self, val):
        if val == '':
            return '{}'

        val = ast.literal_eval(val)
        for key in val:
            val[key]['symbol check'] = self._fmt_driver_symbol_result(val[key]['symbol check'])
            val[key]['symbol check'] = val[key]['symbol check'].replace('\n', '</br>')

        df = pd.DataFrame.from_dict(val, orient='index')
        return df.style.hide_index().\
                  set_table_styles([dict(selector='table', props=[('border','1px solid red')]),
                                    dict(selector='th', props=[('border','1px solid red')]),
                                    dict(selector='td', props=[('border','1px solid red'),
                                                               ('background-color','#CD5C5C'),
                                                               ('color','white')])]).render(head=[])

    def _error_in_supported(self, val):
        if val == '':
            return False
        else:
            val = ast.literal_eval(val)
            for key in val:
                if val[key]['assessment'] == 'Missing' or val[key]['assessment'] == 'yes':
                    return True

        return False

    def to_html(self, rpm_table, file):
        tableFormatter = HTMLTableFormatting()
        styles = tableFormatter.get_style()

        rpm_table['Driver Flag: supported'] = rpm_table['Driver Flag: supported'].astype(str)
        rpm_table['Symbols Check'] = rpm_table['Symbols Check'].astype(str)
        report = dominate.document(title='checking result from soliddriver-checks')

        table_style = f"border:1px solid green;font-size:12px;font-family:sans-serif"
        row_style = f"{table_style}"
        row_warning_style = f"{table_style};border-color: red"
        cell_style = row_style
        cell_warning_style= f"{table_style};border-color: red"
        cell_warn_red_style = f"border:1px solid red;font-size:12px;font-family:sans-serif"
        header_style = f"{table_style}"
        with report:
            with table(style=table_style):
                with tr():
                    cols = rpm_table.columns
                    for col in cols:
                        td(col, style=header_style)

                for i, row in rpm_table.iterrows():
                    supported = row['Driver Flag: supported']
                    symbol_check = row['Symbols Check']
                    curr_row_style = row_style
                    if self._error_in_supported(supported) or symbol_check != '':
                        curr_row_style = row_warning_style
                    with tr(style=curr_row_style):
                        for c in cols:
                            val = row[c]
                            if c == 'Driver Flag: supported':
                                if self._error_in_supported(val):
                                    td(raw(self._fmt_supported_to_html(val)), style=cell_warning_style)
                                else:
                                    td(raw(self._fmt_supported_to_html(val)), style=cell_style)
                            elif c == 'Symbols Check':
                                if val != '{}':
                                    td(raw(self._fmt_symbol_check_to_html(val)), style=cell_warn_red_style)
                                else:
                                    td("", style=cell_style)
                            else:
                                td(val, style=cell_style)

        with open(file, 'w') as f:
            f.write(report.render())

        return

    def to_json(self, rpm_table, file):
        rpm_table.to_json(file, orient='records')

    def to_excel(self, rpm_table, file):
        if os.path.exists(file):
            os.remove(file)

        rpm_table['Driver Flag: supported'] = rpm_table['Driver Flag: supported'].astype(str)
        rpm_table['Symbols Check'] = rpm_table['Symbols Check'].astype(str)

        cols = rpm_table.columns
        xlsx_cols = list(string.ascii_lowercase[0:len(cols)])

        wb = Workbook()
        ws = wb.active
        ws.title = 'solid driver checks'

        general_border = Border(left=Side(border_style="thin",
                                          color='00339966'),
                                right=Side(border_style="thin",
                                          color='00339966'),
                                top=Side(border_style="thin",
                                         color='00339966'),
                                bottom=Side(border_style="thin",
                                            color='00339966'))
        general_align = Alignment(horizontal='left',vertical='top',wrap_text=True)

        for i in range(len(xlsx_cols)):
            cell_no = xlsx_cols[i] + '1'
            ws[cell_no] = cols[i]
            ws[cell_no].border = general_border
            ws[cell_no].alignment = general_align

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
                if cols[col_idx] == "Symbols Check":
                    if val == "{}":
                        val == ""
                    else:
                        val = ast.literal_eval(val)
                        fmt_sc = ""
                        for item in val:
                            fmt_sc = fmt_sc + val[item]['drivers'] + '\n'
                            fmt_sc = fmt_sc + self._fmt_driver_symbol_result(val[item]['symbol check'])
                        val = fmt_sc
                ws[cell_no] = val
                ws[cell_no].border = general_border
                ws[cell_no].alignment = general_align

            supported = row['Driver Flag: supported']
            supported = ast.literal_eval(supported)
            df = pd.DataFrame.from_dict(supported, orient='index')
            driver_count = df.shape[0]
            if driver_count > 0: # format supported information
                for sp_idx, d in df.iterrows():
                    cell_no = xlsx_cols[supported_col_no] + str(curr_row_no + sp_idx)
                    ws[cell_no] = d[0] + ' : ' + d[1]
                    ws[cell_no].border = general_border
                    ws[cell_no].alignment = general_align

            if driver_count > 1: # need merge cell
                for col_idx in range(len(cols)):
                    if col_idx != supported_col_no:
                        start_cell_no = xlsx_cols[col_idx] + str(curr_row_no)
                        end_cell_no = xlsx_cols[col_idx] + str(curr_row_no+driver_count - 1)
                        merge_range = start_cell_no + ":" + end_cell_no
                        ws.merge_cells(merge_range)

            if driver_count == 0:
                curr_row_no += 1
            else:
                curr_row_no += driver_count

        records = len(rpm_table.index) + 1
        support_area = 'F2:F' + str(records)
        support_flag_format = self._formatting.load_support_flag_format()
        na_text = Font(color=support_flag_format['Missing']['font-color'])
        na_fill = PatternFill(bgColor=support_flag_format['Missing']['background-color'])
        na = DifferentialStyle(font=na_text, fill=na_fill)
        yes_text = Font(color=support_flag_format['yes']['font-color'])
        yes_fill = PatternFill(bgColor=support_flag_format['yes']['background-color'])
        yes = DifferentialStyle(font=yes_text, fill=yes_fill)

        support_flag_na_rule = Rule(type='containsText',
                                    operator='containsText',
                                    text='Missing', dxf=na)
        support_flag_yes_rule = Rule(type='containsText',
                                     operator='containsText',
                                     text='yes', dxf=yes)

        ws.conditional_formatting.add(support_area,
                                             support_flag_na_rule)
        ws.conditional_formatting.add(support_area,
                                             support_flag_yes_rule)

        sym_area = 'G2:G' + str(records)
        sym_format = self._formatting.load_symbol_format()
        mismatch_text = Font(color=sym_format['mismatch']['font-color'])
        mismatch_fill = PatternFill(bgColor=sym_format['mismatch']['background-color'])
        mismatch = DifferentialStyle(font=mismatch_text, fill=mismatch_fill)

        mismatch_rule = Rule(type='containsText',
                             operator='containsText',
                             text='.ko', dxf=mismatch)

        ws.conditional_formatting.add(sym_area, mismatch_rule)

        

        wb.save(file)

    def to_pdf(self, rpm_table, file):
        self.to_html(rpm_table, '.tmp.rpms.html')
        pdfkit.from_file('.tmp.rpms.html', file)
        os.remove('.tmp.rpms.html')

    def to_all(self, rpm_table, directory):
        excel_file = os.path.join(directory, 'check_result.xlsx')
        html_file = os.path.join(directory, 'check_result.html')
        pdf_file = os.path.join(directory, 'check_result.pdf')

        if not os.path.exists(directory):
            os.mkdir(directory)
        else:
            if os.path.exists(excel_file):
                os.remove(excel_file)
            if os.path.exists(html_file):
                os.remove(html_file)
            if os.path.exists(pdf_file):
                os.remove(pdf_file)

        self.to_excel(rpm_table, excel_file)
        self.to_html(rpm_table, html_file)
        self.to_pdf(rpm_table, pdf_file)


class DriversExporter:
    def __init__(self, logger):
        self._logger = logger
        self._formatting = FormatConfig()

    def _supported_color(self, value):
        if value == 'yes':
            return '[green]' + value + '[/green]'
        elif value == 'external':
            return value
            # return '[blue]' + value + '[/blue]'
        else:
            return '[red]' + value + '[/red]'

    def _running_color(self, value):
        if value == 'True':
            return '[green]True[/green]'
        else:
            return '[gray]False[gray]'

    def _rpm_info_color(self, value):
        if 'is not owned by any package' in value:
            return '[red]' + value + '[/red]'
        else:
            return value

    def _supported_html_format_handler(self, value):
        value = value.lstrip().rstrip()
        supported = self._formatting.load_support_flag_format()
        bgcolor_yes = supported['yes']['background-color']
        # bgcolor_external = supported['external']['background-color']
        bgcolor_missing = supported['Missing']['background-color']
        if value == 'yes':
            return 'background-color:%s' % bgcolor_yes
        # elif value == 'external':
        #     return 'background-color:%s' % bgcolor_external
        elif value == 'Missing' or value == 'no':
            return 'background-color:%s' % bgcolor_missing

        return ''

    def _running_html_format_handler(self, value):
        running_format = self._formatting.load_running_format()
        bgcolor_true = running_format['true']['background-color']
        bgcolor_false = running_format['false']['background-color']
        if value == 'True':
            return 'background-color:%s' % bgcolor_true

        return 'background-color:%s' % bgcolor_false

    def _rpm_info_html_format_handler(self, value):
        rpm_format = self._formatting.load_rpm_info_format()
        bgcolor_no_rpm = rpm_format['no-rpm']['background-color']
        if 'is not owned by any package' in value:
            return 'background-color:%s' % bgcolor_no_rpm

        return ''

    def to_json(self, driver_tables, file):
        jf = dict()
        for label, driver_table in driver_tables.items():
            if driver_table is not None:
                buff = driver_table.to_json(orient='records')
            else:
                buff = '{}'
            jf[label] = json.loads(buff)

        with open(file, "w") as fp:
            json.dump(jf, fp)

    def to_html(self, driver_tables, file):
        html_table_formatter = HTMLTableFormatting()
        styles = html_table_formatter.get_style()
        body_format = self._formatting.load_body_format()
        context = html()
        with context:
            font_family = body_format["font-family"]
            body_style = 'font-family: %s;' % font_family
            with body(style=body_style):
                for label, driver_table in driver_tables.items():
                    s = driver_table.style.\
                        applymap(self._supported_html_format_handler,
                                 subset=pd.IndexSlice[:, ['Flag: supported']]).\
                        applymap(self._running_html_format_handler,
                                 subset=pd.IndexSlice[:, ['Running']]).\
                        applymap(self._rpm_info_html_format_handler,
                                 subset=pd.IndexSlice[:, ['RPM Information']]).hide_index().\
                        set_table_styles(styles)

                    h1('Solid Driver Checking Result: %s' % label)
                    div(raw(s.render()))

        with open(file, 'w') as f:
            f.write(context.render())

    def to_excel(self, driver_tables, file):
        for server in driver_tables:
            writer = pd.ExcelWriter(file, engine='openpyxl')
            if os.path.exists(file):
                writer = pd.ExcelWriter(file, engine='openpyxl', mode='a')

            driver_tables[server].to_excel(writer, index=False,
                                           sheet_name=server)
            writer.save()
            writer.close()

            workbook = load_workbook(filename=file)
            worksheet = workbook[server]

            records = len(driver_tables[server].index)

            if records < 1:
                workbook.save(file)
                continue

            records = str(len(driver_tables[server].index))

            support_flag_area = 'C2:C' + records
            running_area = 'E2:E' + records
            rpm_info_area = 'F2:F' + records

            support_flag_format = self._formatting.load_support_flag_format()
            na_text = Font(color=support_flag_format['Missing']['font-color'])
            na_fill = PatternFill(bgColor=support_flag_format['Missing']['background-color'])
            na = DifferentialStyle(font=na_text, fill=na_fill)
            yes_text = Font(color=support_flag_format['yes']['font-color'])
            yes_fill = PatternFill(bgColor=support_flag_format['yes']['background-color'])
            yes = DifferentialStyle(font=yes_text, fill=yes_fill)
            # external_text = Font(color=support_flag_format['external']['font-color'])
            # external_fill = PatternFill(bgColor=support_flag_format['external']['background-color'])
            # external = DifferentialStyle(font=external_text, fill=external_fill)
            running_format = self._formatting.load_running_format()
            false_text = Font(color=running_format['false']['font-color'])
            false_fill = PatternFill(bgColor=running_format['false']['background-color'])
            false_format = DifferentialStyle(font=false_text, fill=false_fill)
            true_text = Font(color=running_format['true']['font-color'])
            true_fill = PatternFill(bgColor=running_format['true']['background-color'])
            true_format = DifferentialStyle(font=true_text, fill=true_fill)
            rpm_info_format = self._formatting.load_rpm_info_format()
            no_rpm_text = Font(color=rpm_info_format['no-rpm']['font-color'])
            no_rpm_fill = PatternFill(bgColor=rpm_info_format['no-rpm']['background-color'])
            no_rpm = DifferentialStyle(font=no_rpm_text, fill=no_rpm_fill)
            support_flag_na_rule = Rule(type='containsText',
                                        operator='containsText',
                                        text='Missing', dxf=na)
            # support_flag_external_rule = Rule(type='containsText',
            #                                   operator='containsText',
            #                                   text='external', dxf=external)
            support_flag_yes_rule = Rule(type='containsText',
                                         operator='containsText',
                                         text='yes', dxf=yes)
            running_yes_rule = Rule(type='containsText',
                                    operator='containsText',
                                    text='True', dxf=true_format)
            running_no_rule = Rule(type='containsText',
                                   operator='containsText',
                                   text='False', dxf=false_format)
            no_rpm_rule = Rule(type='containsText', operator='containsText',
                               text='is not owned by any package', dxf=no_rpm)

            worksheet.conditional_formatting.add(support_flag_area,
                                                 support_flag_na_rule)
            # worksheet.conditional_formatting.add(support_flag_area,
            #                                      support_flag_external_rule)
            worksheet.conditional_formatting.add(support_flag_area,
                                                 support_flag_yes_rule)
            worksheet.conditional_formatting.add(running_area,
                                                 running_yes_rule)
            worksheet.conditional_formatting.add(running_area,
                                                 running_no_rule)
            worksheet.conditional_formatting.add(rpm_info_area,
                                                 no_rpm_rule)

            workbook.save(file)

    def to_pdf(self, driver_tables, file):
        self.to_html(driver_tables, '.tmp.rpms.html')
        pdfkit.from_file('.tmp.rpms.html', file)
        os.remove('.tmp.rpms.html')

    def to_all(self, driver_tables, directory):
        excel_file = os.path.join(directory, 'check_result.xlsx')
        html_file = os.path.join(directory, 'check_result.html')
        pdf_file = os.path.join(directory, 'check_result.pdf')

        if not os.path.exists(directory):
            os.mkdir(directory)
        else:
            if os.path.exists(excel_file):
                os.remove(excel_file)
            if os.path.exists(html_file):
                os.remove(html_file)
            if os.path.exists(pdf_file):
                os.remove(pdf_file)

        self.to_excel(driver_tables, excel_file)
        self.to_html(driver_tables, html_file)
        self.to_pdf(driver_tables, pdf_file)
