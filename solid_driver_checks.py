import parameters
from utils import remote_check
from utils import data_exporter
from utils import data_reader
import os
import logging
from rich.logging import RichHandler

if __name__ == "__main__":
    args = parameters.parameter_parse()

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, handlers=[RichHandler()])
    logger = logging.getLogger('rich')
    logger.setLevel(logging.INFO)
    logger.info("Hello")

    if args.dir is not None:
        rpmCheck = data_reader.RPMReader(logger)
        check_result = rpmCheck.GetRPMsInfo(path=args.dir, query=args.query)

        save_to_file = data_exporter.RPMsExporter(logger)

        if args.output == 'terminal':
            save_to_file.to_terminal(check_result)
        elif args.output == 'html':
            save_to_file.to_html(check_result, args.file)
        elif args.output == 'excel':
            save_to_file.to_excel(check_result, args.file)
        elif args.output == 'pdf':
            save_to_file.to_pdf(check_result, args.file)
        elif args.output == 'all':
            save_to_file.to_all(check_result, args.outputdir)
    elif args.rpm is not None:
        rpmCheck = data_reader.RPMReader(logger)
        check_result = rpmCheck.GetRPMInfo(args.rpm)
        print(check_result)
    elif args.system:
        driverCheck = data_reader.DriverReader(logger)
        check_result = driverCheck.get_local_drivers(args.query)

        if args.output == 'terminal':
            export.os_export_to_terminal(check_result)
        elif args.output == 'html':
            export.os_export_to_html(check_result, args.file)
        elif args.output == 'excel':
            result = dict()
            result['Solid Driver Checks'] = check_result
            export.os_export_to_excel(result, args.file)
        elif args.output == 'pdf':
            export.os_export_to_pdf(check_result, args.file)
        elif args.output == 'all':
            export.os_export_to_all(check_result, args.outputdir)
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
            save_to_file.to_pdf(check_result, file)
        elif args.output == 'all':
            save_to_file.to_all(check_result, args.outputdir)

