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
    
    def process(self, data):
        self._progress.console.print(data)
        self._progress.advance(self._task)
    
    def complete(self):
        self._progress.console.print("All KMPs are processed!")


    # def process_kmp(self, kmp):
    #     reader = KMPReader()
    #     anls = KMPAnalysis()
    #     self._terminal_output.prepartion([kmp])
        
    #     raw_info = reader.collect_kmp_data(kmp)
    #     anls_info = anls.kmp_analysis(raw_info)
    #     self._terminal_output.kmp_process(anls_info)
    #     self._terminal_output.complete()
        
    #     return anls_info