import parameters
from utils import input_data
from utils import analysis
from utils import export

if __name__ == "__main__":
    args = parameters.parameter_parse()

    if args.dir != None:
        rpm_files = input_data.get_rpms_from_dir(args.dir)
        df = analysis.analysisRPMs(rpm_files)

        if args.query == 'suse':
            df = analysis.get_suse_support_rpms(df)
        elif args.query == 'vendor':
            df = analysis.get_vendor_support_rpms(df)
        elif args.query == 'unknow':
            df = analysis.get_unknow_rpms(df)
        
        if args.output == 'terminal':
            export.rpms_export_to_terminal(df)
        elif args.output == 'html':
            export.rpms_export_to_html(df, args.file)
        elif args.output == 'pdf':
            export.rpms_export_to_pdf(df, args.file)
        elif args.output == 'excel':
            export.rpms_export_to_excel(df, args.file)
    elif args.rpm != None:
        df = analysis.analysisRPM(args.rpm)
        print(df)
    elif args.system != None:
        df = analysis.analysisOS()

        if args.query == 'suse':
            df = analysis.get_suse_support_drivers(df)
        elif args.query == 'vendor':
            df = analysis.get_vendor_support_drivers(df)
        elif args.query == 'unknow':
            df = analysis.get_unknow_drivers(df)

        if args.output == 'terminal':
            export.os_export_to_terminal(df)
        elif args.output == 'html':
            export.os_export_to_html(df, args.file)
        elif args.output == 'pdf':
            export.os_export_to_pdf(df, args.file)
        elif args.output == 'excel':
            export.os_export_to_excel(df, args.file)
    elif args.driver != None:
        driver_support_flag, running, found, rpm_info = analysis.analysis_driver(args.driver)


