from .data_reader import DriverReader
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from concurrent.futures import ThreadPoolExecutor


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
            drivers, wu_drivers, noinfo_drivers = check_result[ip].result()
            check_result[ip] = {
                "drivers": drivers,
                "weak-update-drivers": wu_drivers,
                "noinfo-drivers": noinfo_drivers,
            }
        progress.console.print("[green]Check completed![/]")

    return check_result
