import pandas as pd
import subprocess
import shlex
from pathlib import Path
import os
import pathlib
import shutil

def analysisOS():
    command = 'find /lib/modules/ -regex ".*\.\(ko\|ko.xz\)$"'
    cmd_driver = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    driver_list, errs = cmd_driver.communicate()
    driver_list = driver_list.split(b'\n')
    driver_list = driver_list[0:len(driver_list) - 1]

    driver_df = pd.DataFrame({"Name":[],
                                 "Path":[],
                                 "Support Flag":[],
                                 "Running":[],
                                 "RPM Information":[]})

    driver_running_list = get_all_running_drivers()
    driver_running_file_list = []

    for driver in driver_running_list:
        driver = str(driver)
        driver = driver[2:len(driver) - 1]
        driver_running_file_list.append(get_running_driver_path(driver))

    for d in driver_list:
        driver = str(d).lstrip().rstrip()
        
        driver = driver[2:len(driver) - 1]
        driver_support_flag = check_support_flag(driver)

        running = driver in driver_running_file_list
        if running is True:
            running = "True"
        else:
            running = "False"

        _, rpm_info = get_rpm_from_driver(driver)

        new_row = {'Name':Path(driver).name, 
                   'Path':driver,
                   'Support Flag': driver_support_flag,
                   'Running': running,
                   'RPM Information': rpm_info}
        driver_df = driver_df.append(new_row, ignore_index=True)
    
    for driver in driver_running_file_list:
        driver = str(driver)
        if driver.startswith('/lib/modules') is False:
            driver_support_flag = check_support_flag(driver)
            running = True
            found, rpm_info = get_rpm_from_driver(driver)
            new_row = {'Name':Path(driver).name, 
                   'Path':driver,
                   'Support Flag': driver_support_flag,
                   'Running': running,
                   'RPM Information': rpm_info}
            driver_df = driver_df.append(new_row, ignore_index=True)

    return driver_df

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

def get_rpm_from_driver(driver):
    command = 'rpm -qf %s' % driver
    command = shlex.split(command)
    rpm_info = subprocess.Popen(command, stdout=subprocess.PIPE)
    info, errs = rpm_info.communicate()
    
    info = str(info)
    info = info[2:len(info) - 3]
    if "is not owned by any package" in info:
        return False, info
    else:
        return True, info

def get_all_running_drivers():
    command = 'cat /proc/modules | awk \'{print $1}\''
    drivers = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    driver_list, errs = drivers.communicate()
    driver_list = driver_list.split(b'\n')
    driver_list = driver_list[0:len(driver_list) - 1]

    return driver_list

def check_support_flag(driver):
    command = '/usr/sbin/modinfo %s' % driver
    command = shlex.split(command)
    support_flag = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpminfo, errs = support_flag.communicate()
    rpminfo = rpminfo.split(b'\n')

    flag = 'N/A'
    for line in rpminfo:
        if line.startswith(b'supported:'):
            flag = str(line)
            flag = flag[len('supported:')+2:len(flag) - 1].rstrip().lstrip()
    
    return flag

def get_basic_info_from_rpm(package):
    command = 'rpm -qpi --nosignature %s' % package
    command = shlex.split(command)
    rpm_qpi = subprocess.Popen(command, stdout=subprocess.PIPE)
    rpm_qpi.wait()

    name = os.path.basename(package)
    signature = ''
    distribution = ''
    vendor = ''
    for line in rpm_qpi.stdout.readlines():
        if line.startswith(b'Signature'):
            sig = str(line)
            sig = sig[0:len(sig) - 3]
            signature = sig[sig.find(':') + 1:]
        if line.startswith(b'Distribution'):
            dis = str(line)
            dis = dis[0:len(dis) - 3]
            distribution = dis[dis.find(':') + 1:]
        if line.startswith(b'Vendor'):
            ven = str(line)
            ven = ven[0:len(ven) - 3]
            vendor = ven[ven.find(':') + 1:]
    
    return name, signature, distribution, vendor

def check_support_flags(drivers):
    drivers_support_flag = dict()
    drivers_support_flag["external"] = []
    drivers_support_flag["yes"] = []
    drivers_support_flag["N/A"] = []
    for driver in drivers:
        drivers_support_flag[check_support_flag(driver)].append(str(driver))
    
    return drivers_support_flag

def get_support_flag_from_rpm(package):
    Path('tmp').mkdir(parents=True, exist_ok=True)
    os.chdir('tmp')

    command = 'rpm2cpio %s | cpio -idmv' % package
    rpm_unpack = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
    rpm_unpack.wait()
    
    rpm_dir = pathlib.Path('.')
    drivers = tuple(rpm_dir.rglob('*.ko'))
    if len(drivers) < 1:
        os.chdir('../')
        shutil.rmtree('tmp')

        return None

    driver_support_flags = check_support_flags(drivers)

    os.chdir('../')
    shutil.rmtree('tmp')

    return driver_support_flags

def analysisRPM(rpm_file):
    name, signature, distribution, vendor = get_basic_info_from_rpm(rpm_file)
    driver_support_flags = get_support_flag_from_rpm(rpm_file)

    return name, signature, distribution, vendor, driver_support_flags

def driver_support_flags_to_string(driver_support_flags):
    driver_support_status = ''

    if driver_support_flags is None:
        return driver_support_status

    for support_type, drivers in driver_support_flags.items():
        if support_type == "external" and len(drivers) > 0:
            driver_support_status = driver_support_status + "Supported by both SUSE and the vendor:\n"
        elif support_type == "yes" and len(drivers) > 0:
            driver_support_status = driver_support_status + "Supported by SUSE:\n"
        elif support_type == "N/A" and len(drivers) > 0:
            driver_support_status = driver_support_status + "Not supported by SUSE:\n"
        for driver in drivers:
            driver_support_status = driver_support_status + "\t" + driver +  "\n"
    
    return driver_support_status

def analysisRPMs(rpm_files):
    driver_df = pd.DataFrame({"Name":[],
                            "Vendor":[],
                            "Signature":[],
                            "Distribution":[],
                            "Driver Support Status":[]})
    for rpm in rpm_files:
        name, signature, distribution, vendor, driver_support_flags = analysisRPM(rpm)
        dsf = driver_support_flags_to_string(driver_support_flags)
        new_row = {'Name':name, 
                    'Vendor':vendor,
                    'Signature':signature,
                    'Distribution':distribution,
                    'Driver Support Status':dsf}
        driver_df = driver_df.append(new_row, ignore_index=True)
    
    return driver_df

def analysis_driver(driver_file):
    drivers_running = get_all_running_drivers()
    drivers_running_files = []
    for driver in drivers_running:
        drivers_running_files.append(get_running_driver_path(driver))
    
    driver_support_flag = check_support_flag(driver_file)
    running = driver in drivers_running_files
    found, rpm_info = get_rpm_from_driver(driver)

    return driver_support_flag, running, found, rpm_info

def get_suse_support_rpms(rpms):
    df = rpms[rpms['Driver Support Status'].str.contains('Supported by SUSE')]
    return df

def get_vendor_support_rpms(rpms):
    df = rpms[rpms['Driver Support Status'].str.contains('Supported by both SUSE and the vendor')]
    return df

def get_unknow_rpms(rpms):
    df = rpms[rpms['Driver Support Status'].str.contains('Not supported by SUSE')]
    return df

def get_suse_support_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag']] is "yes" 
    return rslt_df

def get_vendor_support_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag']] is "external" 
    return rslt_df

def get_unknow_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag']] is "N/A" 
    return rslt_df
