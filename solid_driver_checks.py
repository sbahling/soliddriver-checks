import parameters
from utils import export
from utils import remote_check
from utils import checks
import os
import logging

if __name__ == "__main__":
    args = parameters.parameter_parse()

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if args.dir is not None:
        rpmCheck = checks.RPMChecks(logger)
        check_result = rpmCheck.AnalysisDir(path=args.dir, query=args.query)

        if args.output == 'terminal':
            export.rpms_export_to_terminal(check_result)
        elif args.output == 'html':
            export.rpms_export_to_html(check_result, args.file)
        elif args.output == 'excel':
            export.rpms_export_to_excel(check_result, args.file)
        elif args.output == 'pdf':
            export.rpms_export_to_pdf(check_result, args.file)
        elif args.output == 'all':
            export.rpms_export_to_all(check_result, args.outputdir)
    elif args.rpm is not None:
        rpmCheck = checks.RPMChecks(logger)
        check_result = rpmCheck.analysisRPM(args.rpm)
        print(check_result)
    elif args.system:
        driverCheck = checks.DriverChecks(logger)
        check_result = driverCheck.AnalysisOS(args.query)

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
    elif args.driver is not None:
        driverCheck = checks.DriverChecks(logger)
        driver_support_flag, running, rpm_info = driverCheck.Analysis(args.driver)
        export.print_driver(args.driver, driver_support_flag, running, rpm_info)
    elif args.remote is not None:
        servers = remote_check.get_remote_server_config(args.remote)
        check_result = remote_check.check_remote_servers(logger, servers)

        if args.output == 'terminal':
            export.remote_export_to_terminal(check_result)
        elif args.output == 'html':
            export.remote_export_to_html(check_result, args.file)
        elif args.output == 'excel':
            if os.path.exists(args.file):
                os.remove(args.file)
            export.remote_export_to_excel(check_result, args.file)
