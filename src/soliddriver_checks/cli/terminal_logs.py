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
        pass
