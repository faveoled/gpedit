#-*- coding: utf-8 -*-
'''
Module containing additional GUI code related to the editor.
'''

from PyQt5.QtWidgets import QDialog
from .search_dialog import Ui_Dialog

class SearchDialog(QDialog):

  def __init__(self, editor):
    QDialog.__init__(self, editor)
    self.editor=editor
    self.ui=Ui_Dialog()
    self.ui.setupUi(self)
    self.ui.findEntry.setText(editor.selectedText())

  def find(self):
    expr=self.ui.findEntry.text()
    re=self.ui.findRegex.isChecked()
    cs=self.ui.findCaseSensitive.isChecked()
    wo=self.ui.findMatchWord.isChecked()
    wrap=True
    forward=self.ui.findForward.isChecked()
    return self.editor.findFirst(expr, re, cs, wo, wrap, forward)

  def replace(self):
    txt=self.ui.replaceEntry.text()
    self.editor.replace(txt)
    self.editor.findNext()

  def replaceAll(self):
    txt=self.ui.replaceEntry.text()
    while self.find():
      self.editor.replace(txt)

