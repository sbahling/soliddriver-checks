import subprocess
import shlex
from pathlib import Path
import os
import pathlib
import shutil
import paramiko

def get_cmd_os_drivers():
    return 'find /lib/modules/ -regex ".*\.\(ko\|ko.xz\)$"'
    
def get_cmd_running_drivers():
    return 'cat /proc/modules | awk \'{print $1}\''
    
def get_cmd_running_driver_path(driver):
    return '/usr/sbin/modinfo %s' % driver
    
def get_cmd__rpm_from_driver(driver):
    return 'rpm -qf %s' % driver
    
def get_cmd_modinfo_cmd(driver):
    return '/usr/sbin/modinfo %s' % driver
    
def get_cmd_rpm_info(rpm):
    return 'rpm -qpi --nosignature %s' % rpm
    
def get_cmd_unpack_rpm(rpm):
    return 'rpm2cpio %s | cpio -idmv' % rpm

class CmdProcess:
    def get_os_drivers(self) -> []:
        """Get all drivers under /lib/modules/"""
        pass

    def get_running_drivers(self) -> []:
        """Get all running drivers"""
        pass

    def get_running_driver_path(self) -> str:
        pass

    def get_rpm_from_driver(self, driver: str) -> bool, str:
        pass

    def check_support_flag(self, driver: str) -> str:
        pass

    def format_driver_list(self, drivers) -> []:
        drivers = drivers.split(b'\n')
        drivers = drivers[0:len(driver_list) - 1]

        driver_list = []
        for driver in drivers:
            driver = str(driver).lstrip().rstrip()
            driver = driver[2:len(driver) - 1]
            driver_list.append(driver)
        
        return driver_list
    
    def format_driver_path_from_modinfo(self, modeinfo) -> str:
        for line in modeinfo:
            if line.startswith(b'filename:'):
                file_name = str(line)
                file_name = file_name[file_name.find(":") + 1:len(file_name)-3]

                return file_name.lstrip()
    
        return ""
    
    def format_rpm_name(self, rawresult) -> bool, str:
        info = str(rawresult)
        info = info[2:len(info) - 3]
        if "is not owned by any package" in info:
            return False, info
        else:
            return True, info
    
    def format_support_flag(self, rawresult) -> dict:
        rpminfo = rawresult.split(b'\n')

        flag = 'N/A'
        for line in rpminfo:
            if line.startswith(b'supported:'):
                flag = str(line)
                flag = flag[len('supported:')+2:len(flag) - 1].rstrip().lstrip()
    
        return flag


class LocalCmdProcess(CmdProcess):
    def format_rpm_basic_info(self, rawresult) -> str, str, str:
        signature = ''
        distribution = ''
        vendor = ''
        for line in rawresult:
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
        
        return signature, distribution, vendor

    def get_rpms_from_dir(self, path):
        rpms = []
        for root, _, files in os.walk(path):
            for rpm in files:
                if rpm.endswith(".rpm"):
                    rpmpath = os.path.join(root, rpm)
                    rpms.append(rpmpath)
    
        return rpms

    @CmdProcess.get_os_drivers
    def get_os_drivers(self) -> []:
        """Get all drivers under /lib/modules/"""
        command = get_cmd_os_drivers()
        cmd_driver = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
        drivers, errs = cmd_driver.communicate()
        driver_list = super().format_driver_list(drivers)

        return driver_list

    @CmdProcess.get_running_drivers
    def get_running_drivers(self) -> []:
        """Get all running drivers"""
        command = get_cmd_running_drivers()
        drivers = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                                    stderr=subprocess.PIPE)
        drivers, errs = drivers.communicate()
        driver_list = super().format_driver_list(drivers)
        
        return driver_list

    @CmdProcess.get_running_driver_path
    def get_running_driver_path(self, driver) -> str:
        command = get_cmd_modinfo_cmd(driver)
        command = shlex.split(command)
        info = subprocess.Popen(command, stdout=subprocess.PIPE)
        info.wait()

        driver_path = super().format_driver_path_from_modinfo(info.stdout.readlines())
        
        return driver_path

    @CmdProcess.get_rpm_from_driver
    def get_rpm_from_driver(self, driver: str) -> bool, str:
        command = get_cmd__rpm_from_driver(driver)
        command = shlex.split(command)
        rpm_info = subprocess.Popen(command, stdout=subprocess.PIPE)
        info, errs = rpm_info.communicate()
    
        return super().format_rpm_name(info)

    @CmdProcess.check_support_flag
    def check_support_flag(self, driver: str) -> str:
        command = get_cmd_modinfo_cmd(driver)
        command = shlex.split(command)
        support_flag = subprocess.Popen(command, stdout=subprocess.PIPE)
        rpminfo, errs = support_flag.communicate()
        flag = super().format_support_flag(rpminfo)

        return flag

    def get_basic_info_from_rpm(self, rpm: str) -> str, str, str, str:
        command = get_cmd_rpm_info(rpm)
        command = shlex.split(command)
        rpm_qpi = subprocess.Popen(command, stdout=subprocess.PIPE)
        rpm_qpi.wait()

        name = os.path.basename(rpm)
        signature, distribution, vendor = super().format_rpm_basic_info(rpm_qpi.stdout.readlines())
    
        return name, signature, distribution, vendor

    def get_support_flag_from_rpm(self, rpm: str) -> dict:
        Path('tmp').mkdir(parents=True, exist_ok=True)
        os.chdir('tmp')

        command = get_cmd_unpack_rpm(rpm)
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


class SSHCmdProcess(CmdProcess):
    def __init__(self, ip, user, password, ssh_port):
        self.ip = ip
        self.user = user
        self.password = password
        self.ssh_port = ssh_port

    def connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=self.ip, username=self.user, password=self.password, port=self.ssh_port)

    @CmdProcess.get_os_drivers
    def get_os_drivers(self) -> []:
        """Get all drivers under /lib/modules/"""
        command = get_cmd_os_drivers()
        stdin, stdout, stderr = self.ssh.exec_command(command)
        drivers = stdout.readlines()
        driver_list = super().format_driver_list(drivers)

        return driver_list

    @CmdProcess.get_running_drivers
    def get_running_drivers(self) -> []:
        """Get all running drivers"""
        command = get_cmd_running_drivers()
        stdin, stdout, stderr = self.ssh.exec_command(command)
        drivers = stdout.readlines()
        driver_list = super().format_driver_list(drivers)
        
        return driver_list

    @CmdProcess.get_running_driver_path
    def get_running_driver_path(self) -> str:
        command = get_cmd_modinfo_cmd(driver)
        stdin, stdout, stderr = self.ssh.exec_command(command)

        driver_path = super().format_driver_path_from_modinfo(stdout.readlines())
        
        return driver_path

    @CmdProcess.get_rpm_from_driver
    def get_rpm_from_driver(self, driver: str) -> bool, str:
        command = get_cmd__rpm_from_driver(driver)
        stdin, stdout, stderr = self.ssh.exec_command(command)
    
        return super().format_rpm_name(stdout)

    @CmdProcess.check_support_flag
    def check_support_flag(self, driver: str) -> str:
        command = get_cmd_modinfo_cmd(driver)
        stdin, stdout, stderr = self.ssh.exec_command(command)
        flag = super().format_support_flag(stdout)

        return flag

