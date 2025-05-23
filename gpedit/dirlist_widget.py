#-*- coding: utf-8 -*-
'''
ListWidget that displays the file names of a directory for given filters.
'''

import os
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import pyqtSignal
from glob import glob

class DirListWidget(QListWidget):
  _curdir=None
  filters=None

  fileDoubleClicked=pyqtSignal(str)

  def __init__(self, parent=None, directory='.', filters=['*.dat', '*.txt', '*.out']):
    QListWidget.__init__(self, parent)
    self.filters=filters
    self.changeDirectory(directory)
    self.itemDoubleClicked.connect(self.getFileName)

  def changeDirectory(self, directory):
    self._curdir=directory
    self.clear()
    flist=[]
    for f in self.filters:
      flist+=glob(os.path.join(self._curdir, f))
    flist.sort()
    for fname in flist:
      self.addItem(QListWidgetItem(os.path.basename(fname)))

  def changeFilters(self, newfilters):
    self.filters=newfilters
    self.changeDirectory(self._curdir)

  def getFileName(self, item):
    '''
    :param QListWidgetItem item:
    '''
    fname=item.text()
    self.fileDoubleClicked.emit(fname)
