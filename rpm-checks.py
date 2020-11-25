import os
import sys
import argparse
import subprocess
import shlex
import shutil
from pathlib import Path
import pathlib
from json import JSONEncoder

from get_lenovo_rpms import getDate


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
    unsupportko = []
    for ko in kofiles:
        command = '/usr/sbin/modinfo %s' % ko
        command = shlex.split(command)
        external_flag = subprocess.Popen(command, stdout=subprocess.PIPE)
        external_flag.wait()
        support = False
        for line in external_flag.stdout.readlines():
            if line.startswith(b'supported:      external'):
                support = True
        
        if support == False:
            unsupportko.append(str(ko))

    os.chdir('../')
    shutil.rmtree('tmp')

    return unsupportko

def print_check_result(package, baseinfo, unsupportko):
    print('Package: ' + package)
    print('  |- Base Information')
    for item in baseinfo:
        print('    |- ' + item)
    
    if len(unsupportko) != 0:
        print('  |- Drivers which don\'t support external flag')
        for ko in unsupportko:
            print('    |- ' + ko)
    
    print()

def get_rpms_in_dir(path):
    rpms = []
    for root, _, files in os.walk(path):
        for rpm in files:
            if rpm.endswith(".rpm"):
                rpmpath = os.path.join(root, rpm)
                rpms.append(rpmpath)
    
    return rpms

def serializeToHTML(rpminfo):
    stream = "<html> \
    <title>outputfile</title> <style> \
        \#customers { \
        border-collapse: collapse; \
        width: 100%; \
        } \
            #customers td, #customers th { \
            font-family: Arial, Helvetica, sans-serif;\
            font-size: 12px; \
            border: 1px solid #ddd; \
            padding: 8px; \
        } \
        #customers th { \
        padding-top: 12px; \
        padding-bottom: 12px; \
        text-align: left; \
        background-color: #4CAF50; \
        color: white; \
        }</style>\
        <body> "
    
    rpm_stream = "<tr> \
            <th>Name</th> \
            <th>Vendor</th> \
            <th>Signature</th> \
            <th>Distribution</th> \
            <th>Drivers which don't support external flag</th> \
        </tr>"

    totalRPMs = 0
    buildbySUSE = 0
    no_external_flag = 0
    for rpmpath in rpminfo:
        row = "<tr>"
        baseinfo = check_base_info(rpmpath)
        unsupportko = check_external_flag(rpmpath)

        totalRPMs += 1
        if len(unsupportko) != 0:
            row = "<tr bgcolor=\"red\">"
            no_external_flag += 1
        
        if "SUSE SolidDriver" in baseinfo['vendor']:
            row = "<tr bgcolor=\"green\">"
            buildbySUSE += 1
        row = row + "<td>" + baseinfo['name'] + "</td>" + "<td>" + baseinfo['vendor'] + "</td>" + "<td>" + baseinfo['signature'] + "</td>" + "<td>" + baseinfo['distribution'] + "</td>"
        if len(unsupportko) == 0:
            row = row + "<td>All driver meet SUSE requirements</td>"
        else:
            row = row + "<td>"
            for ko in unsupportko:
                row = row + ko + "</br>"
            row = row + "</td>"
        
        row = row + "</tr>"
        rpm_stream += row

    stream = stream + "<h3>Total RPMs: " + str(totalRPMs) + "</br>RPMs may be built by SUSE: " + str(buildbySUSE) + "</br>" + "RPMs don't support external flag in their kernel models: " + str(no_external_flag) + "</h3></br><table id=\"customers\">" + rpm_stream + "</table></body></html>"
        
    return stream


def parameter_checks():
    description = "Check if driver meet the drivers which are supposed run on SLES"
    usage = "usage"
    parser = argparse.ArgumentParser(usage = usage, description = description)
    parser.add_argument('-d', '--dir', dest="dir", help="rpms in this dirctory")
    parser.add_argument('-f', '--file', dest="file", help="rpm file")
    parser.add_argument('-oh', '--output-html', dest="outputhtml", help="output to html file")
    args = parser.parse_args()
    if args.dir != None:
        if os.path.isdir(args.dir) == False:
            print("Can't find directory at (%s)" % (args.dir))
        else:
            print("will check rpms in (%s)" % (args.dir))
            rpms = get_rpms_in_dir(args.dir)
            return rpms, args.outputhtml
    elif args.file != None:
        if os.path.isfile(args.file) == False:
            print("Can't find file (%s)" % (args.file))
        else:
            print("will check file (%s)" % (args.file))
    else:
        parser.print_help()


if __name__ == "__main__":
    rpms, html = parameter_checks()
    htmlstream = serializeToHTML(rpms)
    f = open(html, "w")
    f.write(htmlstream)
    f.close()

    exit(1)

    date = getDate()

    totalRPMs = 0
    buildbySUSE = 0
    no_external_flag = 0
    for root, dirs, _ in os.walk(date):
        for subdir in dirs:
            for subpath, _, rpms in os.walk(os.path.join(root, subdir)):
                for rpm in rpms:
                    if rpm.endswith(".rpm"):
                        rpmpath = os.path.join(root, subdir, rpm)
                        baseinfo = check_base_info(rpmpath)
                        unsupportko = check_external_flag(rpmpath)
                        print_check_result(rpmpath, baseinfo, unsupportko)
                        # check_buildflags(rpmpath)

                        totalRPMs += 1
                        for item in baseinfo:
                            if item.find('Vendor      : SUSE SolidDriver') >= 0:
                                buildbySUSE += 1
                        
                        if len(unsupportko) != 0:
                            no_external_flag += 1
    

    print_summary(totalRPMs, buildbySUSE, no_external_flag)
                        
    
