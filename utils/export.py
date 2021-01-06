from rich.console import Console
from rich.table import Column, Table

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

def rpms_export_to_html(df, file):
    df.to_html(file, index=False)

def rpms_export_to_pdf(df, file):
    df.to_pdf(file, index=False)

def rpms_export_to_excel(df, file):
    df.to_excel(file, index=False)

def get_support_flag_with_color(support_flag):
    if support_flag == 'yes':
        return '[green]Supported by SUSE[/green]'
    elif support_flag == 'external':
        return '[blue]Supported by both SUSE and vendor[/blue]'
    else:
        return '[red]N/A[/red]'

def get_running_with_color(running):
    if running == "True":
        return '[green]True[/green]'
    else:
        return '[gray]False[/gray]'

def get_rpm_information_with_color(rpm_info):
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
        support_flag = get_support_flag_with_color(row['Support Flag'])
        running = get_running_with_color(row['Running'])
        rpm_info = get_rpm_information_with_color(row['RPM Information'])

        table.add_row(row['Name'], row['Path'], support_flag, running, rpm_info)
    
    console.print(table)

def os_export_to_html(df, file):
    df.to_html(file, index=False)

def os_export_to_pdf(df, file):
    df.to_pdf(file, index=False)

def os_export_to_excel(df, file):
    df.to_excel(file, index=False)