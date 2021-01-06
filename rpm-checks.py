import os
import sys
import argparse
import subprocess
import shlex
import shutil
from pathlib import Path
import pathlib
from rich.console import Console
from rich.table import Column, Table

def check_base_info(package):
    command = 'rpm -qpi --nosignature %s' % package
    command = shlex.split(command)
    rpm_qpi = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_qpi.wait()

    baseinfo = dict()
    baseinfo['name'] = os.path.basename(package)
    for line in rpm_qpi.stdout.readlines():
        if line.startswith(b'Signature'):
            sig = str(line)
            sig = sig[0:len(sig) - 3]
            baseinfo['signature'] = sig[sig.find(':') + 1:]
        if line.startswith(b'Distribution'):
            dis = str(line)
            dis = dis[0:len(dis) - 3]
            baseinfo['distribution'] = dis[dis.find(':') + 1:]
        if line.startswith(b'Vendor'):
            ven = str(line)
            ven = ven[0:len(ven) - 3]
            baseinfo['vendor'] = ven[ven.find(':') + 1:]
    
    return baseinfo

def get_rpm_from_driver(driver):
    command = 'rpm -qf %s' % driver
    command = shlex.split(command)
    rpm_info = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_info.wait()

    info = str(rpm_info.stdout.readlines())
    info = info[3:len(info)-4]
    if "is not owned by any package" in info:
        return False, info
    else:
        return True, info

class DriverInfo:
    def __init__(self, name, path, ko_external_flag, running, foundRPM, rpm_name):
        self.name = name
        self.path = path
        self.ko_external_flag = ko_external_flag
        self.running = running
        self.foundRPM = foundRPM
        self.rpm_name = rpm_name


def check_installed_drivers():
    command = 'find /lib/modules/ -name "*.ko"'
    command = shlex.split(command)
    rpm_kos = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_kos.wait()

    drivers_running = get_all_running_drivers()
    drivers_running_files = []
    for driver in drivers_running:
        drivers_running_files.append(get_running_driver_path(driver))

    kos_info = []
    for line in rpm_kos.stdout.readlines():
        driver = str(line)
        driver = driver[2:len(driver) - 3]
        found, info = get_rpm_from_driver(driver)
        running = driver in drivers_running_files
        if running is True:
            drivers_running_files.remove(driver)
        ko_external_flag = check_external_flag(driver)

        kos_info.append(DriverInfo(Path(driver).name, driver, ko_external_flag, running, found, info))
    
    for driver in drivers_running_files:
        found, info = get_rpm_from_driver(driver)
        ko_external_flag = check_external_flag(driver)

        kos_info.append(DriverInfo(Path(driver).name, driver, ko_external_flag, True, found, info))
    
    return kos_info


def check_buildflags(package):
    command = 'rpm --querytags %s' % package
    command = shlex.split(command)
    rpm_querytags = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_querytags.wait()

    print(rpm_querytags.stdout.readlines())

def check_external_flag(driver):
    command = '/usr/sbin/modinfo %s' % driver
    command = shlex.split(command)
    external_flag = subprocess.Popen(command, stdout=subprocess.PIPE)
    external_flag.wait()
    for line in external_flag.stdout.readlines():
        if line.startswith(b'supported:      external'):
            return 'external'
        elif line.startswith(b'supported:      yes'):
            return 'suse_build'
    
    return 'unknow'


def check_external_flags(drivers):
    drivers_external_flag = dict()
    drivers_external_flag["external"] = []
    drivers_external_flag["suse_build"] = []
    drivers_external_flag["unknow"] = []
    for driver in drivers:
        drivers_external_flag[check_external_flag(driver)].append(str(driver))
    
    return drivers_external_flag

def rpm_check_external_flag(package):
    Path('tmp').mkdir(parents=True, exist_ok=True)
    os.chdir('tmp')

    command = 'rpm2cpio %s | cpio -idmv' % package
    rpm_unpack = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    rpm_unpack.wait()
    
    rpm_dir = pathlib.Path('.')
    kofiles = tuple(rpm_dir.rglob('*.ko'))
    ko_external_flag = check_external_flags(kofiles)

    os.chdir('../')
    shutil.rmtree('tmp')

    return ko_external_flag

def get_rpms_in_dir(path):
    rpms = []
    for root, _, files in os.walk(path):
        for rpm in files:
            if rpm.endswith(".rpm"):
                rpmpath = os.path.join(root, rpm)
                rpms.append(rpmpath)
    
    return rpms

def check_rpm(rpm):
    baseinfo = check_base_info(rpm)
    ko_external_flag = rpm_check_external_flag(rpm)

    return baseinfo, ko_external_flag

class RPMInfo:
    def __init__(self, name, base_info, ko_external_flag):
        self.name = name
        self.base_info = base_info
        self.ko_external_flag = ko_external_flag

def check_dir(path):
    rpms = get_rpms_in_dir(path)
    rpm_summary = dict()
    rpm_summary["total_rpms"] = 0
    rpm_summary["build_by_suse"] = 0
    rpm_summary["no_external_flag"] = 0

    rpms_info = []
    for rpmpath in rpms:
        baseinfo, ko_external_flag = check_rpm(rpmpath)

        rpms_info.append(RPMInfo(Path(rpmpath).name, baseinfo, ko_external_flag))
        
        rpm_summary["total_rpms"] += 1

        if len(ko_external_flag["unknow"]) != 0:
            rpm_summary["no_external_flag"] += 1

        if "SUSE SolidDriver" in baseinfo['vendor']:
            rpm_summary["build_by_suse"] += 1
    
    return rpm_summary, rpms_info


def parameter_checks():
    description = "Check if driver meet the drivers which are supposed run on SLES"
    usage = "usage"
    parser = argparse.ArgumentParser(usage = usage, description = description)
    parser.add_argument('-d', '--dir', dest="dir", help="rpms in this dirctory")
    parser.add_argument('-f', '--file', dest="file", help="rpm file")
    parser.add_argument('-s', '--system', action='store_true', help="check drivers running in the system")
    parser.add_argument('-i', '--installed', action='store_true', help="check drivers installed in the system")
    parser.add_argument('-oh', '--output-html', dest="outputhtml", help="output to html file")
    args = parser.parse_args()
    if args.dir != None:
        if os.path.isdir(args.dir) == False:
            print("Can't find directory at (%s)" % (args.dir))
            exit(1)
    elif args.file != None:
        if os.path.isfile(args.file) == False:
            print("Can't find file (%s)" % (args.file))
            exit(1)
    elif args.system == None:
        parser.print_help()
        exit(1)
    
    return args.dir, args.file, args.outputhtml, args.system, args.installed


def rpms_output_to_html(rpm_summary, rpm_info, outputhtml):
    stream = """<html> 
    <title>outputfile</title> <style> 
        #customers { 
        border-collapse: collapse; 
        width: 100%; 
        } 
            #customers td, #customers th { 
            font-family: Arial, Helvetica, sans-serif;
            font-size: 12px; 
            border: 1px solid #ddd; 
            padding: 8px; 
        } 
        #customers th { 
        padding-top: 12px; 
        padding-bottom: 12px; 
        text-align: left; 
        background-color: #4CAF50; 
        color: white; 
        }</style>
        <body> 
        <h3>Total RPMs: """ + str(rpm_summary['total_rpms']) + "</br>RPMs may be built by SUSE: " + str(rpm_summary['build_by_suse']) + "</br>RPMs don't support external flag in their kernel models: " + str(rpm_summary["no_external_flag"]) + "</h3></br>"
    
    rpm_table = "<tr> \
            <th>Name</th> \
            <th>Vendor</th> \
            <th>Signature</th> \
            <th>Distribution</th> \
            <th>Drivers support status</th> \
        </tr>"

    for rpm in rpm_info:
        row = "<tr>"
                
        if "SUSE SolidDriver" in rpm.base_info['vendor']:
            row = "<tr bgcolor=#4CAF50>"

        if len(rpm.ko_external_flag["unknow"]) != 0:
            row = "<tr bgcolor=\"red\">"

        row = row + "<td>" + rpm.name + "</td>" + "<td>" + rpm.base_info['vendor'] + "</td>" + "<td>" + rpm.base_info['signature'] + "</td>" + "<td>" + rpm.base_info['distribution'] + "</td>"
        row = row + "<td>"
        for support_type, kos in rpm.ko_external_flag.items():
            if support_type == "external" and len(kos) > 0:
                row = row + "Supported by both SUSE and the vendor:"
            elif support_type == "suse_build" and len(kos) > 0:
                row = row + "Supported by SUSE:"
            elif support_type == "unknow" and len(kos) > 0:
                row = row + "Not supported by SUSE:"
            row = row + "</br>"
            for ko in kos:
                row = row + "&nbsp&nbsp&nbsp&nbsp" + ko +  "</br>"
            row = row + "</br>"
        row = row + "</td>"
        
        row = row + "</tr>"
        rpm_table += row

    stream = stream + "<table id=\"customers\">" + rpm_table + "</table></body></html>"

    f = open(outputhtml, "w")
    f.write(stream)
    f.close()

def rpms_output_to_terminal(rpm_summary, rpm_info):
    console = Console()
    console.print("Total RPMs: ", str(rpm_summary['total_rpms']), style = "bold")
    console.print("RPMs may be built by SUSE: ", str(rpm_summary['build_by_suse']), style = "bold green")
    console.print("RPMs don't support external flag in their kernel models: ", str(rpm_summary['no_external_flag']), style = "bold red")

    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name", width=64)
    table.add_column("Vendor", width=12)
    table.add_column("Signature", width=28)
    table.add_column("Distribution", width=12)
    table.add_column("Driver Support Status")
    for rpm in rpm_info:
        driver_support_status = ''
        for support_type, kos in rpm.ko_external_flag.items():
            if support_type == "external" and len(kos) > 0:
                driver_support_status = driver_support_status + "Supported by both SUSE and the vendor:\n"
            elif support_type == "suse_build" and len(kos) > 0:
                driver_support_status = driver_support_status + "Supported by SUSE:\n"
            elif support_type == "unknow" and len(kos) > 0:
                driver_support_status = driver_support_status + "Not supported by SUSE:\n"
            for ko in kos:
                driver_support_status = driver_support_status + "\t" + ko +  "\n"
    
        if len(rpm.ko_external_flag["unknow"]) != 0:
            table.add_row(rpm.name,
                        rpm.base_info['vendor'],
                        rpm.base_info['signature'],
                        rpm.base_info['distribution'], "[red]" + driver_support_status + "[/red]")
        elif "SUSE SolidDriver" in rpm.base_info['vendor']:
            table.add_row(rpm.name,
                        "[green]" + rpm.base_info['vendor'] + "[/green]",
                        rpm.base_info['signature'],
                        rpm.base_info['distribution'], driver_support_status)
        else:
            table.add_row(rpm.name,
                        rpm.base_info['vendor'],
                        rpm.base_info['signature'],
                        rpm.base_info['distribution'], driver_support_status)
    
    console.print(table)

def rpm_output_to_html(name, base_info, ko_external_flag, outputhtml):
    stream = """<html> 
    <title>outputfile</title> <style> 
        #customers { 
        border-collapse: collapse; 
        width: 100%; 
        } 
            #customers td, #customers th { 
            font-family: Arial, Helvetica, sans-serif;
            font-size: 12px; 
            border: 1px solid #ddd; 
            padding: 8px; 
        } 
        #customers th { 
        padding-top: 12px; 
        padding-bottom: 12px; 
        text-align: left; 
        background-color: #4CAF50; 
        color: white; 
        }</style>
        <body>"""
    
    rpm_table = "<tr> \
            <th>Name</th> \
            <th>Vendor</th> \
            <th>Signature</th> \
            <th>Distribution</th> \
            <th>Drivers support status</th> \
        </tr>"

    row = ''
    if "SUSE SolidDriver" in base_info['vendor']:
        row = "<tr bgcolor=#4CAF50>"

    if len(ko_external_flag["unknow"]) != 0:
        row = "<tr bgcolor=\"red\">"
    
    row = row + "<td>" + name + "</td>" + "<td>" + base_info['vendor'] + "</td>" + "<td>" + base_info['signature'] + "</td>" + "<td>" + base_info['distribution'] + "</td>"
    row = row + "<td>"
    for support_type, kos in ko_external_flag.items():
        if support_type == "external" and len(kos) > 0:
            row = row + "Supported by both SUSE and the vendor:"
        elif support_type == "suse_build" and len(kos) > 0:
            row = row + "Supported by SUSE:"
        elif support_type == "unknow" and len(kos) > 0:
            row = row + "Not supported by SUSE:"
        row = row + "</br>"
        for ko in kos:
            row = row + "&nbsp&nbsp&nbsp&nbsp" + ko +  "</br>"
        row = row + "</br>"
    row = row + "</td>"
        
    row = row + "</tr>"
    rpm_table += row

    stream = stream + "<table id=\"customers\">" + rpm_table + "</table></body></html>"

    f = open(outputhtml, "w")
    f.write(stream)
    f.close()

def rpm_output_to_terminal(name, basic_info, ko_external_flag):
    console = Console()

    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name", width=64)
    table.add_column("Vendor", width=12)
    table.add_column("Signature", width=28)
    table.add_column("Distribution", width=12)
    table.add_column("Driver Support Status")
    driver_support_status = ''
    for support_type, kos in ko_external_flag.items():
        if support_type == "external" and len(kos) > 0:
            driver_support_status = driver_support_status + "Supported by both SUSE and the vendor:\n"
        elif support_type == "suse_build" and len(kos) > 0:
            driver_support_status = driver_support_status + "Supported by SUSE:\n"
        elif support_type == "unknow" and len(kos) > 0:
            driver_support_status = driver_support_status + "Not supported by SUSE:\n"
        for ko in kos:
            driver_support_status = driver_support_status + "\t" + ko +  "\n"
    
    if len(ko_external_flag["unknow"]) != 0:
        table.add_row(name,
                    base_info['vendor'],
                    base_info['signature'],
                    base_info['distribution'], "[red]" + driver_support_status + "[/red]")
    elif "SUSE SolidDriver" in base_info['vendor']:
        table.add_row(name,
                    "[green]" + base_info['vendor'] + "[/green]",
                    rpm.base_info['signature'],
                    base_info['distribution'], driver_support_status)
    else:
        table.add_row(name,
                    base_info['vendor'],
                    base_info['signature'],
                    base_info['distribution'], driver_support_status)
    
    console.print(table)

def get_running_driver_path(driver):
    command = '/usr/sbin/modinfo %s' % driver
    command = shlex.split(command)
    info = subprocess.Popen(command, stdout=subprocess.PIPE)
    info.wait()
    for line in info.stdout.readlines():
        if line.startswith(b'filename:'):
            file_name = str(line)
            file_name = file_name[file_name.find(":") + 1:len(file_name)-3]

            return file_name.lstrip()
    
    return ""

def get_all_running_drivers():
    command = 'cat /proc/modules | awk \'{print $1}\''
    drivers = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    drivers.wait()

    driver_list = []
    for line in drivers.stdout.readlines():
        driver = str(line)
        driver_list.append(driver[2:len(driver)-3])

    return driver_list

def drivers_output_to_html(sys_driver_info, outputhtml):
    exit(1)

def drivers_output_to_terminal(sys_driver_info):
    console = Console()

    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name")
    table.add_column("Support Status")
    for d in sys_driver_info:
        if d.external_flag == "external":
            table.add_row("[blue]" + d.name + "[/blue]", "[blue]Is supported by both SUSE and the vendor[/blue]")
        elif d.external_flag == "suse_build":
            table.add_row("[green]" + d.name + "[/green]", "[green]Is supported by SUSE[/green]")
        elif d.external_flag == "unknow":
            table.add_row("[red]" + d.name + "[/red]", "[red]Is not supported by SUSE[/red]")
    
    console.print(table)

class SystemDriverInfo:
    def __init__(self, name, external_flag):
        self.name = name
        self.external_flag = external_flag

def check_all_running_drivers():
    drivers = get_all_running_drivers()

    driver_info = []
    for driver in drivers:
        driver_info.append(SystemDriverInfo(driver, check_external_flag(driver)))
    
    return driver_info

def get_external_flag_cell(external_flag):
    if external_flag == "external":
        return "[blue]Is supported by both SUSE and the vendor[/blue]"
    elif external_flag == "suse_build":
        return "[green]Is supported by SUSE[/green]"
    elif external_flag == "unknow":
        return "[red]Is not supported by SUSE[/red]"

    return "[red]Don't have support flag[/red]"

def get_rpm_info_cell(foundRPM, rpm_name):
    if foundRPM is True:
        return "[green]" + rpm_name + "[/green]"
    else:
        return "[red]" + rpm_name + "[/red]"

def installed_drivers_to_terminal(drivers):
    console = Console()

    table = Table(show_header=True, header_style="bold green", show_lines=True)
    table.add_column("Name")
    table.add_column("Path")
    table.add_column("External Flag")
    table.add_column("Running")
    table.add_column("RPM info")

    for driver in drivers:
        supported = get_external_flag_cell(driver.ko_external_flag)
        rpm_info = get_rpm_info_cell(driver.foundRPM, driver.rpm_name)
        running = "False"
        if driver.running is True:
            running = "True"
        table.add_row(driver.name, driver.path, supported, running, rpm_info)
    
    console.print(table)

def installed_drivers_to_html(drivers, path):
    exit(1)

if __name__ == "__main__":
    path, file, outputhtml, system, installed = parameter_checks()

    if system == True:
        driver_info = check_all_running_drivers()
        if outputhtml != None:
            drivers_output_to_html(driver_info, outputhtml)
        else:
            drivers_output_to_terminal(driver_info)
    elif path != None:
        rpm_summary, rpm_info = check_dir(path)
        if outputhtml != None:
            rpms_output_to_html(rpm_summary, rpm_info, outputhtml)
        else:
            rpms_output_to_terminal(rpm_summary, rpm_info)
    elif file != None:
        base_info, ko_external_flag = check_rpm(file)
        if outputhtml != None:
            rpm_output_to_html(Path(file).name, base_info, ko_external_flag, outputhtml)
        else:
            rpm_output_to_terminal(Path(file).name, base_info, ko_external_flag)
    elif installed != None:
        drivers = check_installed_drivers()
        if outputhtml != None:
            installed_drivers_to_html(drivers, outputhtml)
        else:
            installed_drivers_to_terminal(drivers)
