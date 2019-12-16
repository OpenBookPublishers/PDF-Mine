# Print link metadata of a PDF file, in JSON format
# Nik Sultana, Open Book Publishers, April 2015
#
# Usage:
#   python pdf_metadata.py ../StoriesQuechanOralLiterature.pdf > \
#        sqol-linkmetadata.json

import pdfmine
import sys

filename = sys.argv
pdf = pdfmine.PDFMine(filename[1])
print(pdf.metadata_to_json())
pdf.close()
