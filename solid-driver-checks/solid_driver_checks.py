import parameters
from utils import remote_check
from utils import data_exporter
from utils import data_reader
import os
import logging
import socket
from rich.logging import RichHandler
from rich.live import Live
from utils import terminal_visualizer
from rich.progress import Progress, BarColumn
from rich.style import Style

if __name__ == "__main__":
    args = parameters.parameter_parse()

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, handlers=[RichHandler()])
    logger = logging.getLogger('rich')
    logger.setLevel(logging.INFO)

    if args.dir is not None:
        rpmCheck = data_reader.RPMReader(logger)
        to_terminal = terminal_visualizer.RPMTerminal()
        with Live(to_terminal.get_table()):
            check_result = rpmCheck.get_rpms_info(
                path=args.dir,
                row_handlers=[to_terminal.add_row],
                query=args.query)
        save_to_file = data_exporter.RPMsExporter(logger)

        if args.output == 'html':
            save_to_file.to_html(check_result, args.file)
        elif args.output == 'excel':
            save_to_file.to_excel(check_result, args.file)
        elif args.output == 'pdf':
            save_to_file.to_pdf(check_result, args.file)
        elif args.output == 'all':
            save_to_file.to_all(check_result, args.outputdir)
    elif args.rpm is not None:
        rpmCheck = data_reader.RPMReader(logger)
        check_result = rpmCheck.get_rpm_info(args.rpm)
        print(check_result)
    elif args.system:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        label = '%s (%s)' % (hostname, ip)
        logger.info('Retrieving kernel module data for %s' % label)
        with Progress() as progress:
            driverCheck = data_reader.DriverReader(logger, progress)
            check_result = {label: driverCheck.get_local_drivers(args.query)}
        save_to_file = data_exporter.DriversExporter(logger)
        if args.output == 'html':
            save_to_file.to_html(check_result, args.file)
        elif args.output == 'excel':
            result = dict()
            result['Solid Driver Checks'] = check_result
            save_to_file.to_excel(result, args.file)
        elif args.output == 'pdf':
            save_to_file.to_pdf(check_result, args.file)
        elif args.output == 'all':
            save_to_file.to_all(check_result, args.outputdir)
    elif args.remote is not None:
        servers = remote_check.get_remote_server_config(args.remote)
        check_result = remote_check.check_remote_servers(logger, servers)
        save_to_file = data_exporter.DriversExporter(logger)

        if args.output == 'html':
            save_to_file.to_html(check_result, args.file)
        elif args.output == 'excel':
            if os.path.exists(args.file):
                os.remove(args.file)
            save_to_file.to_excel(check_result, args.file)
        elif args.output == 'pdf':
            save_to_file.to_pdf(check_result, args.file)
        elif args.output == 'all':
            save_to_file.to_all(check_result, args.outputdir)

