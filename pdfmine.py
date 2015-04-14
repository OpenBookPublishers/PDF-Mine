"""
This class finds PDF links, multimedia, and other stuff between two square brackets. It also extracts bookmarks. Useful for making a digital publication.
The previous version used pyPDF but this version uses PDFMiner for text bounding box support
https://github.com/euske/pdfminer/

Copyright 2011 10Layer Software Development Pty (Ltd)
http://10layer.com
Copyright 2015 Open Book Publishers
http://www.openbookpublishers.com

Licensed under the MIT license
http://www.opensource.org/licenses/mit-license.php

Example of use:

import pdfmine
import json
import sys

filename=sys.argv[1]
targetfile=sys.argv[2]
targetdir=sys.argv[3]
pdf=pdfmine.PDFMine(filename)
pdf.save_video(targetdir)
result=pdf.parse_pages()
sections=pdf.get_sections()
f=open(targetfile,"w")
f.write(json.dumps({"pageCount":pdf.pagecount,"pages":result,"sections":sections}))
f.close()
print "All done"

Example of result (Three pages, an internal link on the first to the second page, and an external link on the third):
[[{"dest": 1, "pg": 0, "rect": [34, 362, 380, 34], "external": false}], false, [{"dest": "http://www.10layer.com", "pg": 2, "rect": [82, 929, 686, 610], "external": true}]]
"""
__version__="0.5a"
__author__="Jason Norwood-Young"
__license__="MIT"

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure, LTImage
import os
from pdfminer.pdfpage import PDFPage
import urllib

class PDFMine:
	def __init__(self, filename, verbose = False):
		self.verbose = verbose
		self.result = {}
		self.filename=filename
		self.fp=open(filename, "rb")
		self.parser=PDFParser(self.fp)
		self.doc=PDFDocument(self.parser)
		self.parser.set_document(self.doc)
		self.pagecount=self.pgcount()
		if self.verbose: print "Page count %i" % self.pagecount
		if self.doc.is_extractable:
			if self.verbose: print "Starting extraction of %s" % self.filename
		else:
			print "Oops, error extracting %s" % self.filename
			raise()
		
	def close(self):
		self.fp.close()
		
	def pgcount(self):
		count=0;
		for page in PDFPage.create_pages(self.doc):
		  count = count + 1
		return count
		
	def save_video(self, targetdir):
		"""Saves all your videos to targetdir """
		for page in PDFPage.create_pages(self.doc):
			if (page.annots):
				obj=self.doc.getobj(page.annots.objid)
				for i in obj:
					annotobj=i.resolve()
					try:
						if (annotobj["Subtype"].name=='RichMedia'):
							linktype="media"
							data=annotobj["RichMediaContent"].resolve()
							dataobj=data["Assets"].resolve()
							fstream=dataobj["Names"][1].resolve()
							filename=fstream["F"]
							fdata=fstream['EF']['F'].resolve().get_data()
							f=open(os.path.join(targetdir,filename),"w")
							f.write(fdata)
							f.close()
					except:
						pass
		
	def _rect(self, bbox):
		""" Changes a bounding box into something we can use 
		with HTML (x,y,width,height measured from top left).
		Each of the four values is a percentage, to avoid committing to
		units such as pixels or points at this, um, point."""
		pgbox=self.pgbox
		pgwidth=round(abs(pgbox[0]-pgbox[2]))
		pgheight=round(abs(pgbox[1]-pgbox[3]))
		x=min(bbox[0], bbox[2]) / pgwidth
		y=(pgheight - max(bbox[1], bbox[3])) / pgheight
		width=(max(bbox[0], bbox[2]) - min(bbox[0], bbox[2])) / pgwidth
		height=(max(bbox[1], bbox[3]) - min(bbox[1], bbox[3])) / pgheight

		result={"x":x, "y":y, "width":width, "height":height}
		return result
		
	def _find_objid_pgnum(self, obj):
		"""Given a page, return the page number """
		i=0
		for page in PDFPage.create_pages(self.doc):
			i=i+1
			if self.doc.getobj(page.pageid)==obj:
				return i
		return False
	
	def parse_pages(self):
		result=[]
		i=0
		for page in PDFPage.create_pages(self.doc):
			self.pgbox=page.mediabox
			i=i+1
			if self.verbose: print "==== Page %d ====" % i
			pgbox=self.pgbox
			pgwidth=round(abs(pgbox[0]-pgbox[2]))
			pgheight=round(abs(pgbox[1]-pgbox[3]))
			pg = self._parse_page(page)
			pgdata = {"pgno" : i, "pgwidth" : pgwidth,
			          "pgheight" : pgheight,
			          "links_metadata" : pg['links_metadata'],
			          "pg" : pg['main_result']}
			result.append(pgdata)
		return result
	
	def _parse_page(self, page):
		main_result=[]
		links_metadata=[]
		vids=self._parse_video(page)
		if len(vids)>0:
			main_result.extend(self._parse_video(page))
		links=self._parse_links(page)
		if len(links['main_result'])>0:
			main_result.extend(links['main_result'])
			links_metadata.extend(links['links_metadata'])
		comments=self._parse_comments(page)
		if len(comments)>0:
			main_result.extend(comments)
		return {"links_metadata" : links_metadata,
		        "main_result" : main_result}

	def _parse_comments(self, page):
		result=[]
		rsrcmgr = PDFResourceManager()
		laparams = LAParams()
		device = PDFPageAggregator(rsrcmgr, laparams=laparams)
		interpreter = PDFPageInterpreter(rsrcmgr, device)
		interpreter.process_page(page)
		layout = device.get_result()
		for obj in layout:
			if isinstance(obj, LTTextBox):
				txt=obj.get_text()
				if (txt.find("[[")>=0):
					""" We've found a comment. If it's on top of a rect, return the 
					rect as the bounding box. Else return just the textbox rect """
					rect=self._rect(self._intersects(layout,obj))
					commenttxt={"rect":rect, "comment":txt.replace("]]","").replace("[[","")}
					result.append(commenttxt)
		return result
		
	def _parse_links(self, page):
		main_result=[]
		links_metadata=[]
		if (page.annots):
			obj=self.doc.getobj(page.annots.objid)
			for i in obj:
				annotobj=i.resolve()
				try:
					if (annotobj["Subtype"].name=='Link') and (annotobj.has_key("A")):
						linktype="link"
						if self.verbose: print "Found link"
						obj=annotobj["A"].resolve()
						dest=""

						rect=self._rect(annotobj['Rect'])

						if (obj.has_key('D')):
							linktype="bookmark"
							dest = self._find_objid_pgnum(self.doc.get_dest(obj["D"])[0].resolve())
							metadata = {"dest_page" : '\"' + str(dest) + '\"',
							            "x" : str(rect['x']),
							            "y" : str(rect['y']),
							            "height" : str(rect['height']),
							            "width" : str(rect['width'])}

						if (obj.has_key('URI')):
							dest=obj['URI']
							encoded_uri = urllib.quote_plus(str(dest), safe=':/?=&#;')
							metadata = {"url" : '"' + encoded_uri + '"',
							            "x" : str(rect['x']),
							            "y" : str(rect['y']),
							            "height" : str(rect['height']),
							            "width" : str(rect['width'])}

						link={"rect":rect, "type":linktype,"dest": dest}
						main_result.append(link)
						links_metadata.append(metadata)
				except:
					#FIXME DRY principle
					return {"main_result" : main_result,
					        "links_metadata" : links_metadata}
		return {"main_result" : main_result,
		        "links_metadata" : links_metadata}
			
	def _parse_video(self, page):
		result=[]
		if (page.annots):
			obj=self.doc.getobj(page.annots.objid)
			for i in obj:
				annotobj=i.resolve()
				try:
					if (annotobj["Subtype"].name=='RichMedia'):
						linktype="media"
						rect=self._rect(annotobj['Rect'])
						if self.verbose: print "Found video"
						data=annotobj["RichMediaContent"].resolve()
						dataobj=data["Assets"].resolve()
						fstream=dataobj["Names"][1].resolve()
						filename=fstream["F"]
						link={"rect":rect, "type":linktype, "filename":filename}
						result.append(link)
				except:
					pass
		return result
			
	def _intersects(self, layout, obj):
		""" Finds if the obj is contained within another object on the page """
		origbbox=obj.bbox
		for otherobj in layout:
			if obj!=otherobj:
				otherbbox=otherobj.bbox
				if (origbbox[0]>=otherbbox[0]) and (origbbox[1]>=otherbbox[1]) and (origbbox[2]<=otherbbox[2]) and (origbbox[3]>=otherbbox[3]):
					return otherbbox
		return origbbox
	
	"""
	We search for 'bookmarks' set in Adobe Acrobat
	"""
	def get_sections(self):
		toc=[]
		try:
			outlines = self.doc.get_outlines()
			for (level,title,dest,a,se) in outlines:
				if (dest):
				    objid=dest[0].objid
				    pgobj=dest[0].resolve()
				else:
				    destsobj=a.resolve()
				    pgobj=destsobj["D"][0]
				    objid=pgobj.objid
				x=1;
				for page in PDFPage.create_pages(self.doc):
				    if page.pageid==objid:
				    	toc.append({"name": title, "page": x});
				    x=x+1
		except:
			pass
		return toc

	def test(self):
		print "Starting test on %s" % self.filename
		result=self.parse_pages()
		print result
		print "Found %d pages" % (self.pagecount)
		print self.get_sections()
		print "Metadata to JSON:"
		print metadata_to_json(result)


def link_metadata_to_json(link_mdata):
	result = ""
	if 'dest_page' in link_mdata.keys():
		result += ('\t{\"dest_page\" : ' +
			str(link_mdata["dest_page"]) + ', ' +
			'\"x\" : ' +
			str(link_mdata["x"]) + ', ' +
			'\"y\" : ' +
			str(link_mdata["y"]) + ', ' +
			'\"height\" : ' +
			str(link_mdata["height"]) + ', ' +
			'\"width\" : ' +
			str(link_mdata["width"]) + '}')
	elif 'url' in link_mdata.keys():
		result += ('\t{\"url\" : ' +
			str(link_mdata["url"]) + ', ' +
			'\"x\" : ' +
			str(link_mdata["x"]) + ', ' +
			'\"y\" : ' +
			str(link_mdata["y"]) + ', ' +
			'\"height\" : ' +
			str(link_mdata["height"]) + ', ' +
			'\"width\" : ' +
			str(link_mdata["width"]) + '}')
	else:
		print "Unrecognised link metadata"
		exit (1)
	return result

def pg_metadata_to_json(pgdata):
	result = ('{\"pgno\" : ' + str(pgdata["pgno"]) + ', ' +
		'\"pgwidth\" : ' + str(pgdata["pgwidth"]) + ', ' +
		'\"pgheight\" : ' + str(pgdata["pgheight"]) + ', ' +
		'\"links_metadata\" : [')
	if len(pgdata["links_metadata"]) > 0:
		result += '\n' + link_metadata_to_json(pgdata["links_metadata"][0])
		for link_mdata in pgdata["links_metadata"][1:]:
			result += ',\n' + link_metadata_to_json(link_mdata)
	return result + ']}'

def metadata_to_json(pages_result):
	result = "["
	if len(pages_result) > 0:
		result += pg_metadata_to_json(pages_result[0])
		for pgdata in pages_result[1:]:
			result += ',\n' + pg_metadata_to_json(pgdata)
	return result + "]"
