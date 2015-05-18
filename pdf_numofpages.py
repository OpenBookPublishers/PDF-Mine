# Print the number of pages contained in a PDF file.
# Nik Sultana, Open Book Publishers, May 2015
#
# Usage:
#   python pdf_numofpages.py ../StoriesQuechanOralLiterature.pdf

import pdfmine
import sys

filename = sys.argv
pdf = pdfmine.PDFMine(filename[1])
sys.stdout.write(str(pdf.pagecount))
pdf.close()
