

def get_suse_supported_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag'] is "yes" 
    return rslt_df

def get_both_suse_vendor_supported_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag'] is "external" 
    return rslt_df

def get_unsupported_drivers(drivers):
    rslt_df = drivers.loc[drivers['Support Flag'] is "N/A" 
    return rslt_df
