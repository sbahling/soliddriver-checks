import json
from utils import checks


def get_remote_server_config(file):
    with open(file) as jf:
        servers = json.load(jf)
        return servers['servers']


def check_remote_servers(servers):
    check_result = dict()
    for server in servers:
        if server['check'] == 'False':
            continue

        driverCheck = checks.DriverChecks(ip=server['ip'],
                                          user=server['user'],
                                          password=server['password'],
                                          ssh_port=server['ssh_port'])
        drivers = driverCheck.AnalysisOS(query=server['query'])
        check_result[server['ip']] = drivers

    return check_result
