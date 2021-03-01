import json
from utils import checks


def get_remote_server_config(file):
    with open(file) as jf:
        servers = json.load(jf)
        return servers['servers']


def check_remote_servers(logger, servers):
    check_result = dict()
    for server in servers:
        if server['check'] == 'False':
            continue
        
        logger.info("Start to analysis server: %s", server['ip'])
        driverCheck = checks.DriverChecks(logger = logger, 
                                          ip=server['ip'],
                                          user=server['user'],
                                          password=server['password'],
                                          ssh_port=server['ssh_port'])
        drivers = driverCheck.AnalysisOS(query=server['query'])
        check_result[server['ip']] = drivers
    
    logger.info("Analysis is completed!")

    return check_result
