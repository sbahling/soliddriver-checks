import os

def get_drivers_from_dir(path):
    exit(0)

def get_rpms_from_dir(path):
    rpms = []
    for root, _, files in os.walk(path):
        for rpm in files:
            if rpm.endswith(".rpm"):
                rpmpath = os.path.join(root, rpm)
                rpms.append(rpmpath)
    
    return rpms

def get_drivers_from_os():
    exit(0)

def get_drivers_from_remote(ip, port, username, password):
    exit(0)
