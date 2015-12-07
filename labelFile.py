# -*- coding : utf-8 -*-
#
# Copyright (C) 2011 Michael Pitidis, Hussein Abdulwahid.
#
# This file is part of Labelme.
#
# Labelme is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Labelme is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Labelme.  If not, see <http://www.gnu.org/licenses/>.
#

#from PyQt4.QtGui import *
#from PyQt4.QtCore import *
from PySide.QtGui import *
from PySide.QtCore import *
from lib import newIcon


import json
import os.path
from os import environ
import sys
import ntpath

from base64 import b64encode, b64decode

from xml.etree.cElementTree import Element, SubElement, Comment, tostring, ElementTree
import xml.etree.ElementTree as ET
import xml.etree.cElementTree as et
import re


from xmltools import indent
from shape import DEFAULT_LINE_COLOR_LIST, DEFAULT_FILL_COLOR_LIST
from labelDialog import validWriteTypes


# helpers
def getLines(snip):
   _linesOK = []
   for _line in snip.getiterator('Line'):
      if not re.match(ur'^\s*$', _line.get('Value')):
         _linesOK.append(_line)
   return _linesOK

def pointsFromBox(snip):
   if snip.get('Top') != None: # bounding box
      top = int(snip.get('Top'))
      left = int(snip.get('Left'))
      bottom = int(snip.get('Bottom'))
      right = int(snip.get('Right'))
      return [[left,top], [right,top], [right,bottom], [left,bottom]]
   elif snip.get('polygon') != None:
      return [[int(x[0]),int(x[1])] for x in [z.split(',') for z in snip.get('polygon').replace('(', '').replace(')', '').split(';')]]

def polyFromPoints(points, tag='BBox'):
   ret = []
   if str(tag) == u'Polygon':
      if points[1][0] < points[0][0]: # couterclockwise?
         points = reversed(points)
      ret.append((u'polygon',u';'.join(["("+str(int(x))+","+str(int(y))+")" for x,y in points])))
   elif str(tag) == 'BBox':
      allx = [x for x,y in points]
      ally = [y for x,y in points]
      left = int(min(allx))
      right = int(max(allx))
      top = int(min(ally))
      bottom = int(max(ally))
      ret.append((u'Left', str(left)))
      ret.append((u'Top', str(top)))
      ret.append((u'Right', str(right)))
      ret.append((u'Bottom', str(bottom)))
   else:
      raise RuntimeError('Unknown tag for polyFromPoints <%s>'%tag)
   return ret

def getTop(points):
   return min([x[1] for x in points])

BB = QDialogButtonBox

class LabelTagDialog(QDialog):

    def __init__(self, text="Enter object label", parent=None):
        super(LabelTagDialog, self).__init__(parent)
        layout = QVBoxLayout()
        self.buttonBox = bb = BB(BB.Ok, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        #bb.button(BB.Cancel).setIcon(newIcon('undo'))
        bb.accepted.connect(self.validate)
        #bb.rejected.connect(self.reject)
        self.lbl = QLabel('BBox')

        # Center align text
        self.lbl.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.lbl)

        layout.addWidget(bb)

        self.combo = QComboBox()
        self.combo.addItems([u"Polygon", u"BBox"])

        self.connect(self.combo, SIGNAL('activated(QString)'), self.combo_chosen)
        self.connect(self.combo, SIGNAL('currentIndexChanged(QString)'), self.combo_chosen)
        layout.addWidget(self.combo)
        self.setLayout(layout)

    def getChoice(self):
      return self.lbl.text()

    def combo_chosen(self, text):
        self.lbl.setText(text)

    def validate(self):
         self.accept()


    #def validate(self):
        #if self.edit.text().trimmed():
            #self.accept()

    #def postProcess(self):
        #self.edit.setText(self.edit.text().trimmed())

    #def popUp(self, text='', move=True):
        #self.edit.setText(text)
        #self.edit.setSelection(0, len(text))
        #self.edit.setFocus(Qt.PopupFocusReason)
        #if move:
            #self.move(QCursor.pos())
        #return self.edit.text() if self.exec_() else None



###

class LabelFileError(Exception):
    pass

class LabelFile(object):
   #suffix = '.lif'
   suffixes = [u'.xml'] # '.lif' not used

   def __init__(self, filename=None):
      self.shapes = ()
      self.imagePath = None
      self.imageData = None
      if filename is not None:
         self.load(filename)

   # RM: TODO make something cleaner
   def load(self, filename):
      ext = os.path.splitext(filename)[1].lower()
      if ext == u'.lif':
         self._loadLIF(filename)
      elif ext == u'.xml':
         self._loadDL(filename)
      else:
         raise LabelFileError('Unknown label extension %s'%ext)

   def _loadLIF(self, filename):
      try:
         with open(filename, 'rb') as f:
               data = json.load(f)
               imagePath = data['imagePath']
               imageData = b64decode(data['imageData'])
               lineColor = data['lineColor']
               fillColor = data['fillColor']
               shapes = ((s['label'], s['points'], s['line_color'], s['fill_color'])\
                     for s in data['shapes'])
               # Only replace data after everything is loaded.
               self.shapes = shapes
               self.imagePath = imagePath
               self.imageData = imageData
               self.lineColor = lineColor
               self.fillColor = fillColor
      except Exception, e:
         raise LabelFileError(e)

   def _loadDL(self, filename):
      #try:
      #RM: just read a DocumentList with a single image file, or just the first one TODO
      linesOK = {}
      for _, elem in et.iterparse(filename) :
         if elem.tag == "SinglePage" :
            img = elem.get('FileName')
            pars = list(elem.getiterator('Paragraph'))
            if len(pars) > 0: # read lines
               for k,para in enumerate(pars):
                  linesOK[k] = []
                  linesOK[k].append(getLines(para))
            else: # try lines only
               linesOK['noPara'] = []
               linesOK['noPara'].append(getLines(elem))
            break # just a single image... TODO
      if len(linesOK.keys()) >= 1: # found some lines
         self.imagePath = img
         if not os.path.isfile(img):
            self.imagePath = os.path.join(os.path.split(filename)[0], img)
         with open(self.imagePath, "rb") as image_file:
            self.imageData = image_file.read()
         self.lineColor = DEFAULT_LINE_COLOR_LIST #RM: got from an example, RGB_Alpha
         self.fillColor = DEFAULT_FILL_COLOR_LIST #RM: got from an example
         # shape is a tuple: see above (s['label'], s['points'], s['line_color'], s['fill_color'])
         # points is a list of [x,y] points
         shapes = []
         if linesOK.has_key('noPara'):
            for xl in linesOK['noPara']:
               if xl != []:
                  for line in xl:
                     shapes.append((line.get('Value'), pointsFromBox(line), DEFAULT_LINE_COLOR_LIST, None))
         else:
            for k in sorted(linesOK.keys()):
               #if pars[k].get('Value') is None:
                  #paraT = u''
               #else:
                  #paraT = pars[k].get('Value')
               #shapes.append((u'__P__:'+paraT+str(len(linesOK[k])), pointsFromBox(pars[k]), [255, 255, 224, 128], [255, 255, 224, 32]))
               for xl in linesOK[k]:
                  if xl != []:
                     for line in xl:
                        shapes.append((line.get('Value'), pointsFromBox(line), DEFAULT_LINE_COLOR_LIST, None))
         self.shapes = (x for x in shapes)
      else:
         raise LabelFileError('Did not find any lines in %s'%filename)
      #except Exception, e:
         #raise LabelFileError(e)

   def save(self, filename, shapes, imagePath, imageData,
         lineColor=None, fillColor=None):
      ext = os.path.splitext(str(filename))[1].lower()
      if ext == u'.lif':
         self._saveLIF(filename, shapes, imagePath, imageData,
         lineColor, fillColor)
      elif ext == u'.xml':
         self._saveDL(filename, shapes, imagePath, tag ='BBox')
      else:
         raise LabelFileError('Trying to save with unknown file extension: %s'%ext)

   def _saveLIF(self, filename, shapes, imagePath, imageData,
         lineColor=None, fillColor=None):
      try:
         with open(filename, 'wb') as f:
               json.dump(dict(
                  shapes=shapes,
                  lineColor=lineColor, fillColor=fillColor,
                  imagePath=imagePath,
                  imageData=b64encode(imageData)),
                  f, ensure_ascii=True, indent=2)
      except Exception, e:
         raise LabelFileError(e)

   # RM: we lose the notion of Paragraph and the WT...
   def _saveDL(self, filename, shapes, imagePath, tag):
      try:
         for s in shapes:
            if not s['label'][0] in validWriteTypes:
               raise LabelFileError('Missing write type in line:\n'+s['label'])
         with open(filename, 'wt') as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>' + '\n') # Dirty tweak: XML declaration by hand:
            f.write('<DocumentList>\n')
            sp = Element('SinglePage', {'FileName':imagePath})
            for s in sorted(shapes, key=lambda x: getTop(x['points'])):
               value = s['label']
               line=SubElement(sp, 'Line', {'Value':value})
               for prop,val in polyFromPoints(s['points'], tag):

                  line.set(prop,val)
            indent(sp)
            ElementTree(sp).write(f, encoding="utf-8")
            f.write('</DocumentList>\n')
      except Exception, e:
         raise LabelFileError(e)

   @staticmethod
   def isLabelFile(filename):
      return os.path.splitext(filename)[1].lower() in LabelFile.suffixes
      #f = open('/home/messina/temp/islabel.txt', 'w')
      #ext = os.path.splitext(filename)[1].lower()
      #alors = ext in LabelFile.suffixes
      #print>>f, ext
      #print>>f,alors
      #f.close()
      #return alors
