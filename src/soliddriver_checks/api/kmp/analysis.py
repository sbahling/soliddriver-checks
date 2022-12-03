from .kmp import KMPReader, KMPAnalysis, raw_kmp_to_series, analysis_kmps_to_dataframe

def kmps_analysis_to_dataframe(path, proc_injector=None):
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
            proc_injector.process_item(anls_info)

    if proc_injector is not None:
        proc_injector.complete()
        
    return analysis_kmps_to_dataframe(data)