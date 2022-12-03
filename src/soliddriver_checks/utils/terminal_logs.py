from .data_reader import KMPReader
from .data_analysis import KMPAnalysis


class KMPTerminalOutput:
    def __init__(self, progress):
        self._progress = progress
    
    def prepartion(self, kmps):
        self._task = self._progress.add_task(
            "[italic][bold][green] Checking RPMs "
            + "; Total RPMs: "
            + str(len(kmps)),
            total=len(kmps),
        )
    
    def kmp_process(self, data):
        self._progress.console.print(data)
        self._progress.advance(self._task)
    
    def finish(self):
        self._progress.console.print("Progress is completed!")

class KMPProcessor:
    def __init__(self, terminal_output: KMPTerminalOutput):
        self._terminal_output = terminal_output
    
    def process_kmps(self, path):
        reader = KMPReader()
        anls = KMPAnalysis()
        kmps = reader.get_all_kmp_files(path)
        self._terminal_output.prepartion(kmps)
        data = []
        for kmp in kmps:
            raw_info = reader.collect_kmp_data(kmp)
            anls_info = anls.kmp_analysis(raw_info)
            data.append(anls_info)
            self._terminal_output.kmp_process(anls_info)
        
        self._terminal_output.finish()
        
        return data
    
    def process_kmp(self, kmp):
        reader = KMPReader()
        anls = KMPAnalysis()
        self._terminal_output.prepartion([kmp])
        
        raw_info = reader.collect_kmp_data(kmp)
        anls_info = anls.kmp_analysis(raw_info)
        self._terminal_output.kmp_process(anls_info)
        self._terminal_output.finish()
        
        return anls_info