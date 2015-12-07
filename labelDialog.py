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

from lib import newIcon, labelValidator

# TODO:
# - Calculate optimal position so as not to go out of screen area.

BB = QDialogButtonBox

validWriteTypes = [u'H', u'P', u'M', u'\uff28', u'\uff30', u'\uff2d']

class LabelDialog(QDialog):

    def __init__(self, text="Enter object label", parent=None):
        super(LabelDialog, self).__init__(parent)
        self.edit = QLineEdit()
        self.edit.setText(text)
        self.edit.setValidator(labelValidator())
        self.edit.editingFinished.connect(self.postProcess)
        self.edit.setFixedWidth(600)
        layout = QVBoxLayout()
        layout.addWidget(self.edit)
        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        self.writeTypes = QGroupBox(self)
        #self.writeTypes.setExclusive(True)
        self.hwr = QRadioButton("&Handwritten")
        self.prn = QRadioButton("&Printed")
        self.mix = QRadioButton("&Mixed")

        #self.writeTypes.addButton(hwr)
        #self.writeTypes.addButton(prn)
        #self.writeTypes.addButton(mix)
        #layout.addWidget(self.writeTypes)

        layout.addWidget(self.hwr)
        layout.addWidget(self.prn)
        layout.addWidget(self.mix)
        #vbox.addStretch(100)
        #self.writeTypes.setLayout(vbox)

        self.setLayout(layout)

    def validate(self):
      wt = None
      if self.hwr.isChecked():
         wt = u'H'
      if self.prn.isChecked():
         wt = u'P'
      if self.mix.isChecked():
         wt = u'M'
      txt = self.edit.text().strip()
      if wt and txt:
         self.edit.setText(wt + txt)
         self.accept()

    def cleanWT(self):
      if self.mix.isChecked(): self.mix.toggle()
      if self.prn.isChecked(): self.prn.toggle()
      if self.hwr.isChecked(): self.hwr.toggle()
      self.writeTypes.setChecked(False)
      self.mix.setChecked(False)

    def postProcess(self):
        #txt =
        #wt = None
        ##while not wt:
        #if self.hwr.isChecked():
           #wt = u'H'
        #if self.prn.isChecked():
           #wt = u'P'
        #if self.mix.isChecked():
           #wt = u'M'
        #if wt : txt = wt + txt
        self.edit.setText(self.edit.text().strip())

    def popUp(self, text='', move=True):
      if len(text) > 1: text = text[1:]
      self.edit.setText(text)
      self.edit.setSelection(0, len(text))
      self.edit.setFocus(Qt.PopupFocusReason)
      if move:
         self.move(QCursor.pos())

      return self.edit.text() if self.exec_() else None

