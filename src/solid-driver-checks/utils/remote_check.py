import json
from utils import data_reader
from rich.progress import Progress
from paramiko.ssh_exception import NoValidConnectionsError


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
        try:
            with Progress() as progress:
                reader = data_reader.DriverReader(logger, progress)
                drivers = reader.get_remote_drivers(ip=server['ip'],
                                                    user=server['user'],
                                                    password=server['password'],
                                                    ssh_port=server['ssh_port'],
                                                    query=server['query'])
                check_result[server['ip']] = drivers
        except NoValidConnectionsError:
            logger.error("Can not connect to server: %s", server['ip'])
        finally:
            pass

    logger.info("Analysis is completed!")

    return check_result
