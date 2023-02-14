from .kmp import KMPReader, KMPAnalysis, analysis_kmps_to_dataframe
from .km import KMReader, KMAnalysis
from .filter import km_filter


def kmps_to_dataframe(path, proc_injector=None):
    reader = KMPReader()
    anls = KMPAnalysis()
    kmps = reader.get_all_kmp_files(path)
    if proc_injector is not None:
        proc_injector.prepartion(kmps)

    data = []
    for kmp in kmps:
        raw_info = reader.collect_kmp_data(kmp)
        anls_info = anls.kmp_analysis(raw_info)
        data.append(anls_info)
        if proc_injector is not None:
            proc_injector.process(anls_info)

    if proc_injector is not None:
        proc_injector.complete()

    return analysis_kmps_to_dataframe(data)


def kmp_analysis(kmp_path):
    reader = KMPReader()
    anls = KMPAnalysis()

    raw_info = reader.collect_kmp_data(kmp_path)

    return analysis_kmps_to_dataframe([anls.kmp_analysis(raw_info)])


def kmps_to_json(path, proc_injector=None):
    df = kmps_to_dataframe(path, proc_injector)

    return df.to_json(orient="records")


def kms_to_dataframe(filter=None):
    reader = KMReader()
    anls = KMAnalysis()
    df = anls.kms_analysis(reader.get_all_modinfo())

    if filter is None:
        return df
    else:
        return km_filter(filter, df)


def kms_to_json(df=None, filter=None):
    if df is None:
        df = kms_to_dataframe()

    if filter is None:
        return df.to_json(orient="records")
    else:
        return km_filter(filter, df).to_json(orient="records")
