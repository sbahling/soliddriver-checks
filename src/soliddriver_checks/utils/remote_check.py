from .data_reader import DriverReader
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from paramiko.ssh_exception import NoValidConnectionsError
from concurrent.futures import as_completed, ThreadPoolExecutor


def check_remote_servers(logger, servers):
    check_result = dict()
    progress = Progress(
        "{task.description}",
        SpinnerColumn(),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
    with progress:
        with ThreadPoolExecutor() as pool:
            for server in servers:
                if server["check"] == "False":
                    continue

                reader = DriverReader(progress)
                tinfo = pool.submit(
                    reader.get_remote_drivers,
                    server["ip"],
                    server["user"],
                    server["password"],
                    server["ssh_port"],
                    server["query"],
                )
                check_result[server["ip"]] = tinfo

        for ip in check_result:
            check_result[ip] = check_result[ip].result()
        progress.console.print("[green]Check completed![/]")

    return check_result
