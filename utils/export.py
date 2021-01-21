from rich.console import Console
from rich.table import Column, Table
import pandas as pd


def rpms_export_to_terminal(df):
    console = Console()
    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name", width=64)
    table.add_column("Vendor", width=12)
    table.add_column("Signature", width=28)
    table.add_column("Distribution", width=12)
    table.add_column("Driver Support Status")
    
    for _, row in df.iterrows():
        if "Not supported" in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[red]' + row['Driver Support Status'] + '[/red]')
        elif "Supported by both SUSE and the vendor" in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[blue]' + row['Driver Support Status'] + '[/blue]')
        elif "Supported by SUSE" in row['Driver Support Status']:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], '[green]' + row['Driver Support Status'] + '[/green]')
        else:
            table.add_row(row['Name'], row['Vendor'], row['Signature'], row['Distribution'], row['Driver Support Status'])
    
    console.print(table)

def set_rpm_format_for_html(column):
    if "Not supported" in column:
        return "background-color: red"
    elif "Supported by both SUSE and the vendor" in column:
        return "background-color: blue"
    elif "Supported by SUSE" in column:
        return "background-color: green"
    
    return "background-color: white"

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
    df["Driver Support Status"] = df["Driver Support Status"].str.replace('\n', '</br>')
    df["Driver Support Status"] = df["Driver Support Status"].str.replace('\t', '&nbsp&nbsp&nbsp&nbsp')
    s = df.style.applymap(set_rpm_format_for_html, subset = pd.IndexSlice[:, ['Driver Support Status']]).hide_index()

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
    red_format = workbook.add_format({'bg_color':'red'})
    green_format = workbook.add_format({'bg_color':'green'})
    blue_format = workbook.add_format({'bg_color':'blue'})

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
    if running == "True":
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
    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name", width=64)
    table.add_column("Path", width=64)
    table.add_column("Support Flag", width=28)
    table.add_column("Running", width=12)
    table.add_column("RPM Information")

    for _, row in df.iterrows():
        support_flag = get_support_flag_with_color_for_rich(row['Support Flag'])
        running = get_running_with_color_for_rich(row['Running'])
        rpm_info = get_rpm_information_with_color_for_rich(row['RPM Information'])

        table.add_row(row['Name'], row['Path'], support_flag, running, rpm_info)
    
    console.print(table)

def set_drivers_support_flag_format_for_html(col):
    if col == 'yes':
        return "background-color: green"
    elif col == 'external':
        return "background-color: blue"
    elif col == 'N/A':
        return "background-color: red"
    
    return ""

def set_drivers_running_format_for_html(col):
    if col == 'True':
        return "background-color: green"
    
    return "background-color: gray"

def set_drivers_rpm_info_format_for_html(col):
    if 'is not owned by any package' in col:
        return "background-color: red"
    
    return ""

def os_export_to_html(df, file):
    s = df.style.applymap(set_drivers_support_flag_format_for_html, subset = pd.IndexSlice[:, ['Support Flag']])
    s = s.applymap(set_drivers_running_format_for_html, subset = pd.IndexSlice[:, ['Running']])
    s = s.applymap(set_drivers_rpm_info_format_for_html, subset = pd.IndexSlice[:, ['RPM Information']]).hide_index()

    styles = get_table_render_styles()
    
    s = s.set_table_styles(styles)

    with open(file, 'w') as f:
        f.write(s.render())

def os_export_to_pdf(df, file):
    df.to_pdf(file, index=False)

def os_export_to_excel(df, file):
    writer = pd.ExcelWriter(file, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Solid Driver Checks')
    workbook = writer.book

    worksheet = writer.sheets['Solid Driver Checks']
    red_format = workbook.add_format({'bg_color':'red'})
    green_format = workbook.add_format({'bg_color':'green'})
    blue_format = workbook.add_format({'bg_color':'blue'})
    gray_format = workbook.add_format({'bg_color':'gray'})

    records = str(len(df.index) + 1)
    support_flag_area = 'C2:C' + records
    running_area = 'D2:D' + records
    rpm_info_area = 'E2:E' + records
    worksheet.conditional_format(support_flag_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'N/A',
                                        'format': red_format})
    worksheet.conditional_format(support_flag_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'external',
                                        'format': blue_format})
    worksheet.conditional_format(support_flag_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'yes',
                                        'format': green_format})

    worksheet.conditional_format(running_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'True',
                                        'format': green_format})
    worksheet.conditional_format(running_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'False',
                                        'format': gray_format})
    
    worksheet.conditional_format(rpm_info_area, {'type': 'text',
                                        'criteria': 'containing',
                                        'value': 'is not owned by any package',
                                        'format': red_format})

    writer.save()

def remote_export_to_terminal(driver_collections):
    console = Console()
    for server in driver_collections:
        console.print(server + ' Checking result:')
        os_export_to_terminal(driver_collections[server])


def remote_export_to_html(driver_collections, file):
    pass

def remote_export_to_pdf(driver_collections, file):
    pass

def remote_export_to_excel(driver_collections, file):
    pass