from rich.live import Live
from rich.table import Table
from rich.progress import Progress


class RPMTerminal:
    def __init__(self):
        self._table = Table(show_header=True,
                            header_style='bold green', show_lines=True)
        self._table.add_column('Name', width=32)
        self._table.add_column('Path', width=64)
        self._table.add_column('Vendor', width=12)
        self._table.add_column('Signature', width=28)
        self._table.add_column('Distribution', width=12)
        self._table.add_column('Driver Flag: supported')
        self._table.add_column('Symbols Check')

    def get_table(self):
        return self._table

    def add_row(self, dataset):
        name = dataset[0]
        path = dataset[1]
        vendor = dataset[2]
        signature = dataset[3]
        distribution = dataset[4]
        supported = dataset[5]
        symbols = dataset[6]

        ds_formatting = ''
        for driver in supported.split('\n'):
            values = driver.split(': ')

            if len(values) < 2:
                ds_formatting += '[red]' + driver + '[/red]' + '\n'
            elif values[1] == 'yes':
                ds_formatting += '[green]' + driver + '[/green]' + '\n'
            elif values[1] == 'external':
                ds_formatting += '[blue]' + driver + '[/blue]' + '\n'
            elif values[1] == 'no' or values[1] == 'Missing':
                ds_formatting += '[red]' + driver + '[/red]' + '\n'

        if symbols != '':
            symbols = '[red]' + symbols + '[/red]'

        self._table.add_row(name, path, vendor,
                            signature, distribution, ds_formatting, symbols)
