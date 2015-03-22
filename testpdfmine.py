import pdfmine
import sys

filename=sys.argv
pdf=pdfmine.PDFMine(filename[1])
# pdf.save_video(filename[2]) FIXME untested feature
pdf.test()
pdf.close()
