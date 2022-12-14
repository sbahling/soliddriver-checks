import pandas as pd
from .kmp import KMPReader, raw_kmp_to_series


def kmps_to_dataframe(path, proc_injector=None):
    reader = KMPReader()
    kmps = reader.get_all_kmp_files(path)
    if proc_injector is not None:
        proc_injector.prepartion(kmps)

    df = pd.DataFrame()
    for kmp in kmps:
        raw_info = reader.collect_kmp_data(kmp)
        row = raw_kmp_to_series(raw_info)
        df = pd.concat([df, row.to_frame().T], ignore_index=True)
        if proc_injector is not None:
            proc_injector.process_item(raw_info)

    if proc_injector is not None:
        proc_injector.complete()

    return df


def kmps_to_json(path, proc_injector=None):
    pass

def km_to_dataframe(proc_injector=None):
    pass

def km_to_json():
    pass

def remote_km_to_json(remote_info, proc_injector=None):
    pass

