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
            baseinfo['signature'] = sig[sig.find(':') + 1:]
        if line.startswith(b'Distribution'):
            dis = str(line)
            baseinfo['distribution'] = dis[dis.find(':') + 1:]
        if line.startswith(b'Vendor'):
            ven = str(line)
            baseinfo['vendor'] = ven[ven.find(':') + 1:]
    
    return baseinfo


def check_buildflags(package):
    command = 'rpm --querytags %s' % package
    command = shlex.split(command)
    rpm_querytags = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_querytags.wait()

    print(rpm_querytags.stdout.readlines())

def check_external_flag(package):
    Path('tmp').mkdir(parents=True, exist_ok=True)
    os.chdir('tmp')

    command = 'rpm2cpio %s | cpio -idmv' % package
    rpm_unpack = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    rpm_unpack.wait()
    
    rpm_dir = pathlib.Path('.')
    kofiles = tuple(rpm_dir.rglob('*.ko'))
    ko_external_flag = dict()
    ko_external_flag["external"] = []
    ko_external_flag["suse_build"] = []
    ko_external_flag["unknow"] = []
    for ko in kofiles:
        command = '/usr/sbin/modinfo %s' % ko
        command = shlex.split(command)
        external_flag = subprocess.Popen(command, stdout=subprocess.PIPE)
        external_flag.wait()
        flag = False
        for line in external_flag.stdout.readlines():
            if line.startswith(b'supported:      external'):
                ko_external_flag["external"].append(str(ko))
                flag = True
            elif line.startswith(b'supported:      yes'):
                ko_external_flag["suse_build"].append(str(ko))
                flag = True
        if flag == False:
            ko_external_flag["unknow"].append(str(ko))

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
    ko_external_flag = check_external_flag(rpm)

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
    parser.add_argument('-s', '--system', dest="system", help="check drivers in the system")
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
    else:
        parser.print_help()
        exit(1)
    
    return args.dir, args.file, args.outputhtml, args.system


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
            if support_type == "external":
                row = row + "Supported by both SUSE and the vendor:"
            elif support_type == "suse_build":
                row = row + "Supported by SUSE:"
            elif support_type == "unknow":
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

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Name")
    table.add_column("Vendor")
    table.add_column("Signature")
    table.add_column("Distribution")
    table.add_column("Driver Support Status")
    for rpm in rpm_info:
        driver_support_status = ''
        for support_type, kos in rpm.ko_external_flag.items():
            if support_type == "external":
                driver_support_status = driver_support_status + "Supported by both SUSE and the vendor:\n"
            elif support_type == "suse_build":
                driver_support_status = driver_support_status + "Supported by SUSE:\n"
            elif support_type == "unknow":
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
        if support_type == "external":
            row = row + "Supported by both SUSE and the vendor:"
        elif support_type == "suse_build":
            row = row + "Supported by SUSE:"
        elif support_type == "unknow":
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

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Name")
    table.add_column("Vendor")
    table.add_column("Signature")
    table.add_column("Distribution")
    table.add_column("Driver Support Status")
    driver_support_status = ''
    for support_type, kos in ko_external_flag.items():
        if support_type == "external":
            driver_support_status = driver_support_status + "Supported by both SUSE and the vendor:\n"
        elif support_type == "suse_build":
            driver_support_status = driver_support_status + "Supported by SUSE:\n"
        elif support_type == "unknow":
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

if __name__ == "__main__":
    path, file, outputhtml, system = parameter_checks()

    if path != None:
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


