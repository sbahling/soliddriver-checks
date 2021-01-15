import command_process
import pandas as pd
from pathlib import Path

class RPMChecks:
    def Analysis(self, path):
        self.cmdProcess = command_process.LocalCmdProcess()

    def get_suse_support_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains('Supported by SUSE')]
        return df

    def get_vendor_support_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains('Supported by both SUSE and the vendor')]
        return df

    def get_unknow_rpms(self, rpms):
        df = rpms[rpms['Driver Support Status'].str.contains('Not supported by SUSE')]
        return df

    def AnalysisDir(self, path, query='all'):
        driver_df = pd.DataFrame({"Name":[],
                            "Vendor":[],
                            "Signature":[],
                            "Distribution":[],
                            "Driver Support Status":[]})
        
        rpm_files = self.cmdProcess.get_rpms_from_dir(path)

        for rpm in rpm_files:
            name, signature, distribution, vendor, driver_support_flags = self.analysisRPM(rpm)
            dsf = self.cmdProcess.driver_support_flags_to_string(driver_support_flags)
            new_row = {'Name':name, 
                    'Vendor':vendor,
                    'Signature':signature,
                    'Distribution':distribution,
                    'Driver Support Status':dsf}
            driver_df = driver_df.append(new_row, ignore_index=True)
    
        if query == 'all':
            return driver_df
        elif query == 'suse':
            return self.get_suse_support_rpms(driver_df)
        elif query == 'vendor':
            return self.get_vendor_support_rpms(driver_df)
        elif query == 'unknow':
            return self.get_unknow_rpms(driver_df)
        
        return driver_df

    def analysisRPM(self, rpm_file):
        name, signature, distribution, vendor = self.cmdProcess.get_basic_info_from_rpm(rpm_file)
        driver_support_flags = self.cmdProcess.get_support_flag_from_rpm(rpm_file)

        return name, signature, distribution, vendor, driver_support_flags

    def driver_support_flags_to_string(self, driver_support_flags):
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

class DriverChecks:
    def __init__(self, ip='127.0.0.1', user='', password='', ssh_port=22):
        if ip == '127.0.0.1':
            self.cmdProcess = command_process.LocalCmdProcess()
        else:
            self.cmdProcess = command_process.SSHCmdProcess(ip, user, password, ssh_port)
        
        self.driver_df = pd.DataFrame({"Name":[],
                                 "Path":[],
                                 "Support Flag":[],
                                 "Running":[],
                                 "RPM Information":[]})

    def get_suse_support_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Support Flag']] is "yes" 
        return rslt_df

    def get_vendor_support_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Support Flag']] is "external" 
        return rslt_df

    def get_unknow_drivers(self):
        rslt_df = self.driver_df.loc[self.driver_df['Support Flag']] is "N/A" 
        return rslt_df

    def AnalysisOS(self, query='all'):
        driver_list = self.cmdProcess.get_os_drivers()
        driver_running_list = self.cmdProcess.get_running_drivers()
        driver_running_file_list = []
        for driver in driver_running_list:
            driver_running_file_list.append(self.cmdProcess.get_running_driver_path(driver))

        for driver in driver_list:
            running = driver in driver_running_file_list
            if running is True:
                running = "True"
            else:
                running = "False"
        
            _, rpm_info = self.cmdProcess.get_rpm_from_driver(driver)

            new_row = {'Name':Path(driver).name, 
                   'Path':driver,
                   'Support Flag': self.cmdProcess.check_support_flag(driver),
                   'Running': running,
                   'RPM Information': rpm_info}
            self.driver_df = self.driver_df.append(new_row, ignore_index=True)
    
        for driver in driver_running_file_list:
            if driver.startswith('/lib/modules') is False:
                driver_support_flag = self.cmdProcess.check_support_flag(driver)
                running = True
                _, rpm_info = self.cmdProcess.get_rpm_from_driver(driver)
                new_row = {'Name':Path(driver).name, 
                   'Path':driver,
                   'Support Flag': driver_support_flag,
                   'Running': running,
                   'RPM Information': rpm_info}
                self.driver_df = self.driver_df.append(new_row, ignore_index=True)

        if query == 'all':
            return self.driver_df
        elif query == 'suse':
            return self.get_suse_support_drivers()
        elif query == 'vendor':
            return self.get_vendor_support_drivers()
        elif query == 'unknow':
            return self.get_unknow_drivers()

        return self.driver_df

    def Analysis(self, path):
        drivers_running = self.cmdProcess.get_running_drivers()
        drivers_running_files = []
        for driver in drivers_running:
            drivers_running_files.append(self.cmdProcess.get_running_driver_path(driver))
    
        driver_support_flag = self.cmdProcess.check_support_flag(path)
        running = driver in drivers_running_files
        found, rpm_info = self.cmdProcess.get_rpm_from_driver(driver)

        return driver_support_flag, running, found, rpm_info
