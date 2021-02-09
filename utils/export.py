from rich.console import Console
from rich.table import Table
from pathlib import Path
import pandas as pd
import os
from dominate.tags import body, div, html, h1
from dominate.util import raw
from openpyxl.styles import PatternFill, Font
from openpyxl.styles.differential import DifferentialStyle
from openpyxl import load_workbook
from openpyxl.formatting.rule import Rule


def rpms_export_to_terminal(df):
    console = Console()
    table = Table(show_header=True, header_style='bold green', show_lines=True)
    table.add_column('Name', width=64)
    table.add_column('Vendor', width=12)
    table.add_column('Signature', width=28)
    table.add_column('Distribution', width=12)
    table.add_column('Driver Support Status')

    for _, row in df.iterrows():
        if 'Not supported' in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[red]' + row['Driver Support Status'] + '[/red]')
        elif 'Supported by both SUSE and the vendor' in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[blue]' + row['Driver Support Status'] + '[/blue]')
        elif 'Supported by SUSE' in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[green]' + row['Driver Support Status'] + '[/green]')
        else:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], row['Driver Support Status'])

    console.print(table)


def set_rpm_format_for_html(column):
    if 'Not supported' in column:
        return 'background-color: red'
    elif 'Supported by both SUSE and the vendor' in column:
        return 'background-color: blue'
    elif 'Supported by SUSE' in column:
        return 'background-color: green'

    return 'background-color: white'


def get_table_render_styles():
    styles = [
        dict(selector='table', props=[('border', '1px solid green'),
                                      ('border-collapse', 'collapse')]),
        dict(selector='th', props=[('font-size', '12pt'),
                                   ('font-family', 'arial'),
                                   ('background-color', 'green'),
                                   ('border', '1px solid green')]),
        dict(selector='td', props=[('font-size', '10pt'),
                                   ('font-family', 'arial'),
                                   ('border', '1px solid green')])
    ]

    return styles


def rpms_export_to_html(df, file):
    df['Driver Support Status'] = df['Driver Support Status'].str.replace('\n', '</br>')
    df['Driver Support Status'] = df['Driver Support Status'].str.replace('\t', '&nbsp&nbsp&nbsp&nbsp')
    s = df.style.applymap(set_rpm_format_for_html,
                          subset=pd.IndexSlice[:, ['Driver Support Status']],
                          ).hide_index()

    styles = get_table_render_styles()

    s = s.set_table_styles(styles)

    with open(file, 'w') as f:
        f.write(s.render())

def rpms_export_to_pdf(df, file):
    df.to_pdf(file, index=False)

def rpms_export_to_excel(df, file):
    writer = pd.ExcelWriter(file, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Solid Driver Checks')
    workbook = writer.book

    # workbook = load_workbook(file)
    worksheet = writer.sheets['Solid Driver Checks']
    red_format = workbook.add_format({'bg_color': 'red'})
    green_format = workbook.add_format({'bg_color': 'green'})
    blue_format = workbook.add_format({'bg_color': 'blue'})

    area = 'E2:E' + str(len(df.index) + 1)
    worksheet.conditional_format(area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'Not supported',
                                        'format': red_format})
    worksheet.conditional_format(area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'Supported by both SUSE and the vendor',
                                        'format': blue_format})
    worksheet.conditional_format(area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'Supported by SUSE',
                                        'format': green_format})

    writer.save()


def get_support_flag_with_color_for_rich(support_flag):
    if support_flag == 'yes':
        return '[green]Supported by SUSE[/green]'
    elif support_flag == 'external':
        return '[blue]Supported by both SUSE and vendor[/blue]'
    else:
        return '[red]N/A[/red]'


def get_running_with_color_for_rich(running):
    if running == 'True':
        return '[green]True[/green]'
    else:
        return '[gray]False[/gray]'


def get_rpm_information_with_color_for_rich(rpm_info):
    if 'is not owned by any package' in rpm_info:
        return '[red]' + rpm_info + '[/red]'
    else:
        return rpm_info


def os_export_to_terminal(df):
    console = Console()
    table = Table(show_header=True, header_style='bold green', show_lines=True)
    table.add_column('Name', width=64)
    table.add_column('Path', width=64)
    table.add_column('Support Flag', width=28)
    table.add_column('Running', width=12)
    table.add_column('RPM Information')

    for _, row in df.iterrows():
        support_flag = get_support_flag_with_color_for_rich(row['Support Flag'])
        running = get_running_with_color_for_rich(row['Running'])
        rpm_info = get_rpm_information_with_color_for_rich(row['RPM Information'])

        table.add_row(row['Name'], row['Path'], support_flag, running, rpm_info)

    console.print(table)


def set_drivers_support_flag_format_for_html(col):
    if col == 'yes':
        return 'background-color: green'
    elif col == 'external':
        return 'background-color: blue'
    elif col == 'N/A':
        return 'background-color: red'

    return ''


def set_drivers_running_format_for_html(col):
    if col == 'True':
        return 'background-color: green'

    return 'background-color: gray'


def set_drivers_rpm_info_format_for_html(col):
    if 'is not owned by any package' in col:
        return 'background-color: red'

    return ''


def os_export_to_html(df_collection, file):
    context = html()
    with context:
        with body():
            for key in df_collection:
                h1('Solid Driver Checking Result: ' + key)
                s = df_collection[key].style.applymap(set_drivers_support_flag_format_for_html,
                                                      subset=pd.IndexSlice[:, ['Support Flag']])
                s = s.applymap(set_drivers_running_format_for_html,
                               subset=pd.IndexSlice[:, ['Running']])
                s = s.applymap(set_drivers_rpm_info_format_for_html,
                               subset=pd.IndexSlice[:, ['RPM Information']]).hide_index()

                styles = get_table_render_styles()

                s = s.set_table_styles(styles)
                div(raw(s.render()))

    with open(file, 'w') as f:
        f.write(context.render())

def os_export_to_pdf(df, file):
    df.to_pdf(file, index=False)

def os_export_to_excel(df, file, sheet='Solid Driver Checks'):
    writer = pd.ExcelWriter(file, engine='openpyxl')
    if os.path.exists(file):
        writer = pd.ExcelWriter(file, engine='openpyxl', mode='a')

    df.to_excel(writer, index=False, sheet_name=sheet)
    writer.save()
    writer.close()

    workbook = load_workbook(filename=file)
    worksheet = workbook[sheet]

    records = str(len(df.index) + 1)
    support_flag_area = 'C2:C' + records
    running_area = 'D2:D' + records
    rpm_info_area = 'E2:E' + records

    red_text = Font(color='9C0006')
    red_fill = PatternFill(bgColor='FFC7CE')
    red = DifferentialStyle(font=red_text, fill=red_fill)
    green_text = Font(color='00008000')
    green_fill = PatternFill(bgColor='0099CC00')
    green = DifferentialStyle(font=green_text, fill=green_fill)
    blue_text = Font(color='000000FF')
    blue_fill = PatternFill(bgColor='0099CCFF')
    blue = DifferentialStyle(font=blue_text, fill=blue_fill)
    grey_text = Font(color='00808080')
    grey_fill = PatternFill(bgColor='00C0C0C0')
    grey = DifferentialStyle(font=grey_text, fill=grey_fill)
    support_flag_na_rule = Rule(type='containsText', operator='containsText', text='N/A', dxf=red)
    support_flag_external_rule = Rule(type='containsText', operator='containsText', text='external', dxf=blue)
    support_flag_yes_rule = Rule(type='containsText', operator='containsText', text='yes', dxf=green)
    running_yes_rule = Rule(type='containsText', operator='containsText', text='True', dxf=green)
    running_no_rule = Rule(type='containsText', operator='containsText', text='False', dxf=grey)
    no_rpm_rule = Rule(type='containsText', operator='containsText', text='is not owned by any package', dxf=red)

    worksheet.conditional_formatting.add(support_flag_area, support_flag_na_rule)
    worksheet.conditional_formatting.add(support_flag_area, support_flag_external_rule)
    worksheet.conditional_formatting.add(support_flag_area, support_flag_yes_rule)
    worksheet.conditional_formatting.add(running_area, running_yes_rule)
    worksheet.conditional_formatting.add(running_area, running_no_rule)
    worksheet.conditional_formatting.add(rpm_info_area, no_rpm_rule)

    workbook.save(file)


def remote_export_to_terminal(driver_collections):
    console = Console()
    for server in driver_collections:
        console.print(server + ' Checking result:')
        os_export_to_terminal(driver_collections[server])


def remote_export_to_html(driver_collections, file):
    os_export_to_html(driver_collections, file)

def remote_export_to_pdf(driver_collections, file):
    pass

def remote_export_to_excel(driver_collections, file):
    for server in driver_collections:
        os_export_to_excel(driver_collections[server], file, server)


def print_rpm():
    pass


def print_driver(path, driver_support_flag, running, rpm_info):
    console = Console()
    console.print('Name: ' + Path(path).name, style='bold green')
    style = 'bold green'
    if running is False:
        style = 'bold grey85'
    console.print('Running: ', running, style=style)
    if driver_support_flag == 'yes':
        console.print('Support Status: Driver is supported by SUSE', style='bold green')
    elif driver_support_flag == 'external':
        console.print('Support Status: Driver is supported by both SUSE and vendor', style='bold blue')
    elif driver_support_flag == 'N/A':
        console.print("Support Status: Driver don't have support flag!", style='bold red')
    else:
        console.print('Support Status: Unknow, driver support flag is ', driver_support_flag, style='bold red')
    style='bold green'
    if 'is not owned by any package' in rpm_info:
        console.print(rpm_info, style='bold red')
    else:
        console.print('Driver is in rpm: ' + rpm_info, style='bold green')
