import os
import subprocess
import shlex
import shutil
from pathlib import Path
import pathlib

from get_lenovo_rpms import getDate


def check_base_info(package):
    command = 'rpm -qpi --nosignature %s' % package
    command = shlex.split(command)
    rpm_qpi = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_qpi.wait()

    baseinfo = []
    for line in rpm_qpi.stdout.readlines():
        if line.startswith(b'Signature'):
            baseinfo.append(str(line))
        if line.startswith(b'Distribution'):
            baseinfo.append(str(line))
        if line.startswith(b'Vendor'):
            baseinfo.append(str(line))
    
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

    command = 'rpm2cpio ../%s | cpio -idmv' % package
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

def print_summary(totalRPMs, buildbySUSE, no_external_flag):
    print('####################################################################################################')
    print('Total RPMs: ' + str(totalRPMs))
    print('RPMs may be built by SUSE: ' + str(buildbySUSE))
    print('RPMs don\'t support external flag in their Kernel Models: ' + str(no_external_flag))
    print('####################################################################################################')

if __name__ == "__main__":
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
                        
    
