import tabula 
import pandas as pd

class PDFReader:
    def __init__(self):
        self.pdf_to_df("samples/2026-MW37.pdf", '47')

        input('Press ENTER to exit')

    def pdf_to_df(self, filename, pages):
        data = tabula.read_pdf(filename, pages=pages, lattice=True, multiple_tables=True)
        df = pd.concat(data,ignore_index=True)
        df.to_excel(f"{filename}{pages}.xlsx")
        print(data)

_pdf = PDFReader()