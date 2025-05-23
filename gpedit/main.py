#-*- coding: utf-8 -*-
'''
Main GUI startup scripts and class.
'''

import os, sys
from time import sleep
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QColorDialog, QDialog, \
                        QAction, QMenu, QLabel, QVBoxLayout, QMessageBox, QInputDialog
from PyQt5.QtGui import QPixmap, QFont, QFontMetrics, QColor, QIcon, QPainter
from PyQt5.QtPrintSupport import QPrintDialog
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QUrl, QSettings, pyqtSlot, QFileSystemWatcher
from PyQt5 import Qsci
try:
  from PyQt5 import QtWebKitWidgets
  OLD_WEBWIDGET=True
except ImportError:
  from PyQt5 import QtWebEngineWidgets #@UnusedImport
  OLD_WEBWIDGET=False

from .main_window import Ui_MainWindow
from .actions import SET_ACTIONS, PALETTS, TEMPLATE
from .config import cfg, add_user_macro, del_user_macro, write_config
from .gplexer import setLexer
from .gnuplot_interface import GnuplotInterface
from .editor import SearchDialog
from . import icons_rc #@UnusedImport
try:
  import popplerqt5
except ImportError:
  popplerqt5=None

class MainWindow(QMainWindow):
  preview_term=None
  term_options=None
  _default_term_options=dict(
                           enhanced='',
                           size='',
                           font='font "Arial,14"',
                           title='',
                           close='',
                           n=1,
                           )
  last_row=0
  last_script=None
  openFile=None
  fileChanged=False
  n_terms=0

  window_idx=1
  ignore_marker=-1
  error_marker=-1
  plotimage_pixmaps=None
  _images_waiting=None
  _scriptRunning=False

  def __init__(self):
    QMainWindow.__init__(self)
    self.ui=Ui_MainWindow()
    self.ui.setupUi(self)
    self.setupScintilla()
    self.buildMenus()

    self.term_options=dict(self._default_term_options)
    self.gpi=GnuplotInterface(self)
    self.gpi.lineSend.connect(self.gnuplotLineSend)
    self.gpi.lineExecuted.connect(self.gnuplotLineExecuted)
    self.gpi.scriptFinished.connect(self.gnuplotScriptFinished)
    self.gpi.imagesFinished.connect(self.showImages)
    self.gpi.mousePicked.connect(self.positionPicked)
    self.gpi.start()

    self.readSettings()

    old_resize=self.ui.gnuplotImageScroller.resizeEvent
    def gISResize(event):
      old_resize(event)
      self.displayPixmaps()
    self.ui.gnuplotImageScroller.resizeEvent=gISResize

    self._active_path=os.getcwd()
    self._path_watcher=QFileSystemWatcher([self._active_path], self)
    self._path_watcher.directoryChanged.connect(self._update_folder)


  def setupScintilla(self):
    ed=self.ui.editor
    ed.setUtf8(True)
    ed.setBraceMatching(Qsci.QsciScintilla.SloppyBraceMatch)


    # wrap lines only at spaces
    ed.setWrapMode(Qsci.QsciScintilla.WrapWord)
    try:
      ed.setWrapVisualFlags(Qsci.QsciScintilla.WrapFlagInMargin, indent=4)
    except AttributeError:
      pass
    ed.setWrapIndentMode(Qsci.QsciScintilla.WrapIndentFixed)

    # Margin 0 is used for line numbers
    font=QFont('Sans', 10, QFont.Normal)
    fontmetrics=QFontMetrics(font)
    ed.setMarginsFont(font)
    ed.setMarginWidth(0, fontmetrics.width("000")+6)
    ed.setMarginLineNumbers(0, True)
    ed.setMarginsBackgroundColor(QColor("#cccccc"))

    # behavior of marginc area
    ed.setMarginSensitivity(1, True)
    ed.marginClicked.connect(self.detectorMarginClicked)
    self.ignore_marker=ed.markerDefine(Qsci.QsciScintilla.RightTriangle)
    ed.setMarkerBackgroundColor(QColor("#eeee11"), self.ignore_marker)
    self.error_marker=ed.markerDefine(Qsci.QsciScintilla.Rectangle)
    ed.setMarkerBackgroundColor(QColor("#ee1111"), self.error_marker)

    setLexer(ed)

  def buildMenus(self):
    self.action_macros={}
    action=QAction('encoding', self.ui.menuSet)
    action.triggered.connect(self.insertEncoding)
    self.ui.menuSet.addAction(action)
    self._addMenuEntries(self.ui.menuSet, SET_ACTIONS)
    self._addMenuEntries(self.ui.menuPalette, PALETTS)
    self._addMenuEntries(self.ui.menuCommands, cfg.items('user macros'))

  def _addMenuEntries(self, menu, entries):
    for entry in entries:
      if entry is None:
        menu.addSeparator()
        continue
      if len(entry)==2:
        label, item=entry
        icon=None
      else:
        label, icon_name, item=entry
        icon=QIcon(icon_name)
      if type(label) is str:
        try: # fix for python 3
          label=str(label, 'utf8')
        except TypeError:
          pass
      if isinstance(item, str):
        if type(item) is str:
          try:
            item=str(item, 'utf8')
          except TypeError:
            pass
        if icon:
          action=QAction(icon, label, menu)
        else:
          action=QAction(label, menu)
        action.triggered.connect(self.insertMacro)
        self.action_macros[action]=item
        menu.addAction(action)
      else:
        if icon:
          submenu=QMenu(icon, label, menu)
        else:
          submenu=QMenu(label, menu)
        menu.addMenu(submenu)
        self._addMenuEntries(submenu, item)

  def insertMacro(self):
    ed=self.ui.editor
    ed.insert(self.action_macros[self.sender()]+'\n')
    l, c=ed.getCursorPosition()
    ed.setCursorPosition(l+1, c)

  def insertEncoding(self):
    ed=self.ui.editor
    ed.insert('set encoding '+self.ui.encoding.currentText()+'\n')
    l, c=ed.getCursorPosition()
    ed.setCursorPosition(l+1, c)

  @pyqtSlot(int, int)
  def editorCursorMoved(self, row, col):
    if row!=self.last_row:
      self.last_row=row
      if self.ui.autoPreview.isChecked() and not self._scriptRunning:
        self.evaluateScript(False)

  @pyqtSlot(str, int)
  def gnuplotLineSend(self, text, lno):
    self.ui.gnuplotInput.insertPlainText(text)

  @pyqtSlot(bool, str, int)
  def gnuplotLineExecuted(self, result, output, lno):
    output=str(output).strip()
    if output!='':
      self.ui.gnuplotOutput.insertPlainText(output+'\n')
    if lno>=0 and not result:
      self.ui.editor.markerAdd(lno-1, self.error_marker)

  @pyqtSlot()
  def gnuplotScriptFinished(self):
    if self._images_waiting is None:
      self.ui.plotImage.setText('Run Script')
      self._scriptRunning=False

  def analyzeScript(self):
    ed=self.ui.editor
    txt=str(self.ui.editor.text())
    txt_lines=list(map(str.strip, txt.splitlines()))
    # removed marked lines
    line_idx=list(range(len(txt_lines)))
    i=0
    while i<len(txt_lines):
      if txt_lines[i].strip().startswith('#'):
        txt_lines.pop(i)
        line_idx.pop(i)
        continue
      # join lines ended with \\ as one command
      while txt_lines[i].strip().endswith('\\'):
        if len(txt_lines)==(i+1):
          txt_lines[i]=txt_lines[i].strip().rstrip(',\\ ')
        else:
          txt_lines[i]=txt_lines[i].strip()+'\n'+txt_lines.pop(i+1)
          line_idx.pop(i+1)
      if ed.markersAtLine(line_idx[i])&(self.ignore_marker+1):
        txt_lines.pop(i)
        line_idx.pop(i)
        continue
      # join data after a plot "-" into one command
      if txt_lines[i].strip().startswith('plot "-"') or\
         txt_lines[i].strip().startswith("plot '-'") or\
         txt_lines[i].strip().startswith('splot "-"') or\
         txt_lines[i].strip().startswith("splot '-'"):
        while i<len(txt_lines):
          add_line=txt_lines.pop(i+1)
          line_idx.pop(i+1)
          if add_line.strip().startswith('e'):
            break
          else:
            txt_lines[i]+='\n'+add_line
        txt_lines[i]+='\ne'
      i+=1
    return line_idx, txt_lines

  @pyqtSlot()
  @pyqtSlot(bool)
  def evaluateScript(self, force=True, reset_after=True):
    if self._scriptRunning:
      self.gpi.stopScript()
      self.ui.plotImage.setText('Run Script')
      self._scriptRunning=False
      return
    ed=self.ui.editor
    line_idx, txt_lines=self.analyzeScript()
    #
    if (self.last_script==txt_lines and not force) or len(txt_lines)==0:
      return
    else:
      for i in range(ed.lines()):
        ed.markerDelete(i, self.error_marker)
    self._images_waiting=None
    self._scriptRunning=True
    self.ui.plotImage.setText('Stop Run')
    self.last_script=txt_lines
    self.gpi.clear()
    self.ui.gnuplotInput.clear(); self.ui.gnuplotOutput.clear()

    self.window_idx=1
    for i, line in enumerate(txt_lines):
      if self.checkIgnore(line):
        self.analyzeLine(line)
        continue
      if line.strip().startswith('load'):
        try:
          self.analyzeLoad(line)
        except:
          pass
      self.gpi.write(line, line_idx[i]+1)
    for i in range(self.window_idx, self.n_terms+1):
      self.gpi.write(self.preview_term%dict(list(self._default_term_options.items())+
                                        [('n', i), ('close', 'close')]))
    self.n_terms=self.window_idx-1
    if reset_after:
      self.gpi.write(None,-1) # indicate that script ends here

  def analyzeLoad(self, srcline):
    name=srcline.strip().split(None, 1)[1].strip()
    if name.startswith('"'):
      name=name.rsplit('"', 1)[0][1:]
    else:
      name=name.rsplit("'", 1)[0][1:]
    txt=open(name, 'r').read()
    for line in txt.splitlines():
        if line.strip().startswith('load'):
          self.analyzeLoad(line)
        else:
          self.analyzeLine(line)

  def analyzeLine(self, line):
    if line.strip().startswith('set'):
      sopts=sopts=line.split('set ', 1)[1].strip()
      if sopts.startswith('term'):
        self.analyzeTerm(line)
      if sopts.startswith('output') and ('"' in line or "'" in line):
        self.gpi.write(self.preview_term%dict(list(self.term_options.items())+[('n', self.window_idx)]))
        if self.ui.applySize.isChecked(): sleep(0.1) #wait for window to be resized
        self.window_idx+=1

  @pyqtSlot()
  def evaluateScriptImage(self):
    if self._scriptRunning:
      self.gpi.stopScript()
      self.ui.plotImage.setText('Run Script')
      self._scriptRunning=False
      return
    ed=self.ui.editor
    line_idx, txt_lines=self.analyzeScript()
    for i in range(ed.lines()):
      ed.markerDelete(i, self.error_marker)
    self._scriptRunning=True
    self.ui.plotImage.setText('Stop Run')
    self.gpi.clear()
    self.ui.gnuplotInput.clear(); self.ui.gnuplotOutput.clear()

    fnames=[]
    fname=None
    for lno, line in zip(line_idx, txt_lines):
      if 'set' in line and 'output' in line:
        if not ('"' in line or "'" in line):
          continue
        if '"' in line:
          fname=line.split('"')[1]
        else:
          fname=line.split("'")[1]
        fnames.append(fname)
      self.gpi.write(line, lno+1)
    self.gpi.write('unset output')
    self.gpi.write(None, len(fnames)) # indicate that script ends here and contains images
    self._images_waiting=fnames

  def checkIgnore(self, line):
    if line.strip().startswith('set '):
      sopts=line.split('set ', 1)[1].strip()
      if sopts.startswith('output'):
        return True
      elif sopts.startswith('term'):
        return True
    return False

  def analyzeTerm(self, line):
    line=line.split('#')[0]
    self.term_options=dict(self._default_term_options)
    size_multiply=[1., 0.5, 0.25][self.ui.sizeMultiply.currentIndex()]
    if 'noenhanced' in line:
      self.term_options['enhanced']='noenhanced'
    elif 'enhanced' in line:
      self.term_options['enhanced']='enhanced'
    if self.ui.applyFont.isChecked() and 'font' in line:
      sidx=line.index('font')
      sstr=None
      for i in range(line.index('font'), len(line)):
        if sstr is None and line[i] in ['"', "'"]:
          sstr=line[i]
          sidx=i+1
        elif line[i]==sstr:
          eidx=i
          break
      csplit=line[sidx:eidx].split(',')
      font=csplit[0]
      if len(csplit)>1 and self.ui.applySize.isChecked():
        try:
          size=int(round(float(csplit[1])*size_multiply))
        except ValueError:
          size=14
      else:
        size=14
      if 'pdfcairo' in line:
        scale=0.5
        if 'fontscale' in line:
          scale=float(line.split('fontscale')[1].strip().split()[0])
        size*=scale*5.5
      self.term_options['font']='font "%s,%i"'%(font, size)
    if self.ui.applySize.isChecked() and 'size' in line:
      sidx=line.index('size')+4
      for i in range(sidx+5, len(line)):
        if not line[i] in ['c', 'm', ',', '.', ' ']+list(map(str, list(range(10)))):
          i-=1
          break
      try:
        w, h=line[sidx:i+1].split(',')
        if 'cm' in w:
          w=182.8*float(w.rstrip('cm '))
          h=182.8*float(h.rstrip('cm '))
        elif 'pdf' in line:
          # default pdf size is in inches
          w=72.*float(w)
          h=72.*float(h)
        else:
          w=float(w)
          h=float(h)
        w*=size_multiply
        h*=size_multiply
      except ValueError:
        pass
      else:
        self.term_options['size']='size %s,%s'%(w, h)

  def clearImages(self):
    vbox=self.ui.gnuplotImageHolder.layout()
    for i in reversed(list(range(vbox.count()))):
      vbox.itemAt(i).widget().close()

  @pyqtSlot()
  def showImages(self):
    self.ui.plotImage.setText('Run Script')
    self._scriptRunning=False
    fnames=self._images_waiting
    self.plotimage_pixmaps=[]
    self.plotimage_labels=[]
    widget=self.ui.gnuplotImageHolder
    vbox=widget.layout()
    self.clearImages()
    ftxt=''
    for fname in fnames:
      fname=os.path.abspath(str(fname))
      if not os.path.exists(fname):
        continue
      ftxt+=fname+';'
      label=QLabel(widget)
      vbox.addWidget(label)

      if fname.endswith('.pdf'):
        if popplerqt5 is None:
          label.setText("Can't display pdf without poppler library")
          self.plotimage_labels.append(label)
          self.plotimage_pixmaps.append(None)
          continue
        doc=popplerqt5.Poppler.Document.load(fname)
        img=doc.page(0).renderToImage(300., 300.) # render pdf using 300dpi
        pixmap=QPixmap()
        pixmap.convertFromImage(img)
      elif fname.endswith('.svg'):
        renderer=QSvgRenderer(fname)
        pixmap=QPixmap(renderer.defaultSize())
        painter=QPainter(pixmap)
        renderer.render(painter)
      else:
        pixmap=QPixmap(fname)
      self.plotimage_pixmaps.append(pixmap)
      self.plotimage_labels.append(label)
    self.ui.fileName.setText(ftxt[:-1])
    self._images_waiting=None
    self.displayPixmaps()

  def displayPixmaps(self):
    if self.plotimage_pixmaps is None:
      return
    for pix, label in zip(self.plotimage_pixmaps, self.plotimage_labels):
      if pix is None:
        continue
      w, h=pix.width(), pix.height()
      if self.ui.scaleToFit.isChecked():
        scale=min((self.ui.gnuplotImageScroller.width()-20.)/w,
                  (self.ui.gnuplotImageScroller.height()-20.)/h)
      else:
        try:
          scale=float(self.ui.scaling.text())/100.
        except ValueError:
          scale=1.
      if scale!=1.:
        pix=pix.scaled(w*scale, h*scale,
                       transformMode=Qt.SmoothTransformation)
      label.setGeometry(0, 0, pix.width(), pix.height())
      label.setPixmap(pix)
      label.show()

  def detectorMarginClicked(self, nmarker, nline, modifiers):
    ed=self.ui.editor
    if ed.markersAtLine(nline)&(self.ignore_marker+1):
        ed.markerDelete(nline, self.ignore_marker)
    elif ed.markersAtLine(nline)==0:
        ed.markerAdd(nline, self.ignore_marker)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  ################### Menu Actions #################
  def commentSelection(self):
    ed=self.ui.editor
    sel=ed.getSelection()
    txt_lines=str(ed.text()).splitlines()
    for nline in range(sel[0], min(len(txt_lines), sel[2]+1)):
      txt_lines[nline]='#'+txt_lines[nline]
    ed.setText('\n'.join(txt_lines))
    ed.setSelection(*sel)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  def uncommentSelection(self):
    ed=self.ui.editor
    sel=ed.getSelection()
    txt_lines=str(ed.text()).splitlines()
    for nline in range(sel[0], sel[2]+1):
      txt_lines[nline]=txt_lines[nline].lstrip(' #')
    ed.setText('\n'.join(txt_lines))
    ed.setSelection(*sel)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  def ignoreSelection(self):
    ed=self.ui.editor
    sel=ed.getSelection()
    for nline in range(sel[0], sel[2]+1):
      ed.markerAdd(nline, self.ignore_marker)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  def unignoreSelection(self):
    ed=self.ui.editor
    sel=ed.getSelection()
    for nline in range(sel[0], sel[2]+1):
      ed.markerDelete(nline, self.ignore_marker)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  def pasteColor(self):
    color=QColorDialog.getColor(parent=self)
    r, g, b, _a=color.getRgb()
    cstring='#%02x%02x%02x'%(r, g, b)
    self.ui.editor.insert(cstring)

  def pickPosition(self):
    self.evaluateScript(True, reset_after=False)
    self.pickmsg=QDialog(self)
    vbox=QVBoxLayout(self.pickmsg)
    self.pickmsg.setLayout(vbox)
    vbox.addWidget(QLabel('Pick Position on Plot', self.pickmsg))
    self.pickmsg.show()
    self.gpi.pickPosition()

  @pyqtSlot(float, float)
  def positionPicked(self, x, y):
    self.ui.plotImage.setText('Run Script')
    self._scriptRunning=False
    self._images_waiting=None
    self.pickmsg.close()
    self.ui.editor.insert('%g,%g'%(x, y))
    self.activateWindow()

  def newDocument(self):
    self.openFile=None
    self.ui.editor.clear()

  @pyqtSlot()
  def insertTemplate(self):
    if 'TMP' in os.environ:
      template=TEMPLATE%os.environ['TMP'].replace('\\', '\\\\')
    elif 'TMP' in os.environ:
      template=TEMPLATE%os.environ['TMP'].replace('\\', '\\\\')
    else:
      template=TEMPLATE%'/tmp'
    self.ui.editor.insert(template)
    if self.ui.autoPreview.isChecked():
      self.evaluateScript(False)

  def changeEncoding(self, new_encoding):
    txt=str(self.ui.editor.text())
    if 'set encoding' in txt:
      tsplit=txt.split('set encoding', 1)
      txt=tsplit[0]+'set encoding %s\n'%new_encoding+'\n'.join(tsplit[1].splitlines()[1:])
      self.ui.editor.setText(txt)
      if self.ui.autoPreview.isChecked():
        self.evaluateScript()

  def fileOpen(self, fname=None):
    self._checkSave()
    if not fname:
      fname=QFileDialog.getOpenFileName(self, 'Select Script to Open',
                                       os.path.abspath(os.curdir),
                                       'Gnuplot Script (*.gp *.gpl *.txt);;All (*)')[0]
      if fname=='':
        return
    fname=os.path.abspath(str(fname))
    self.openFile=fname
    fdir=os.path.dirname(fname)
    self._changeDir(fdir)
    ftxt=open(fname, 'rb').read()
    self.ui.editor.setText('')
    if b'set encoding' in ftxt:
      encd=ftxt.split(b'set encoding')[-1].splitlines()[0].strip()
      encd_idx=self.ui.encoding.findText(str(encd))
      if encd_idx>=0:
        self.ui.encoding.setCurrentIndex(encd_idx)
    self.ui.editor.setText(ftxt.decode(self.ui.encoding.currentText(), 'replace'))
    self.ui.editor.setModified(False)
    self.clearImages()
    if self.ui.autoPreview.isChecked():
      self.evaluateScript()

  def fileSave(self):
    self.fileSaveAs(self.openFile)

  def fileSaveAs(self, fname=None):
    if not fname:
      if self.openFile:
        path=os.path.dirname(self.openFile)
      else:
        path=os.path.abspath(os.curdir)
      fname=QFileDialog.getSaveFileName(self, 'Save File As',
                                        path,
                                        'Gnuplot Script (*.gp *.gpl *.txt);;All (*)')[0]
    if fname:
      fname=os.path.abspath(fname)
      open(fname, 'wb').write(self.ui.editor.text().encode(self.ui.encoding.currentText(),
                                                            'replace'))
      self.openFile=fname
      fdir=os.path.dirname(fname)
      self._changeDir(fdir)
      self.ui.editor.setModified(False)

  def _checkSave(self):
    if self.fileChanged:
      save=QMessageBox.question(self, 'Save Changes',
                            'The current document has been modified, do you want to save it?',
                            QMessageBox.Yes|QMessageBox.No, QMessageBox.Yes)
      if save==QMessageBox.Yes:
        self.fileSaveAs(self.openFile)

  def _changeDir(self, fdir):
    os.chdir(fdir)
    self.gpi.write("cd '%s'"%fdir)
    self.ui.filenameList.changeDirectory(fdir)
    self._path_watcher.removePath(self._active_path)
    self._active_path=fdir
    self._path_watcher.addPath(self._active_path)

  def _update_folder(self):
    self.ui.filenameList.changeDirectory(self._active_path)

  def textModified(self, modified):
    if not self.fileChanged==modified:
      self.fileChanged=modified
      if modified:
        self.setWindowTitle('Gnuplot Editor - %s*'%self.openFile)
      else:
        self.setWindowTitle('Gnuplot Editor - %s'%self.openFile)

  def aboutDialog(self):
    QMessageBox.information(self, 'About Gnuplot Editor...',
              'Gnuplot editor is writtern by\nArtur Glavic\n\nLicensed under GPL v.3')

  def gnuplotHelp(self):
    dia=QDialog(self)
    dia.setWindowTitle('Gnuplot Manual')
    verticalLayout=QVBoxLayout(dia)
    dia.setLayout(verticalLayout)
    if OLD_WEBWIDGET:
      webview=QtWebKitWidgets.QWebView(dia)
    else:
      webview=QtWebEngineWidgets.QWebEngineView(dia)
    webview.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'htmldocs', 'index.html')))
    verticalLayout.addWidget(webview)
    # set width of the page to fit the document and height to the same as the main window
    dia.resize(700, 900)
    dia.show()

  def addMacro(self):
    ed=self.ui.editor
    name, ok=QInputDialog.getText(self, 'Add Macro', 'Please enter a name for your new macro:')
    if ok:
      name=str(name)
      txt=str(ed.text()).splitlines()[ed.getCursorPosition()[0]]
      add_user_macro(name, txt)
      self._addMenuEntries(self.ui.menuCommands, [[name, txt]])

  def deleteMacro(self):
    item_list=self.ui.menuCommands.actions()[3:]
    name_list=[item.text() for item in item_list]
    delitem, ok=QInputDialog.getItem(self, 'Delete Macro', 'Select Macro to delete', name_list,
                                     editable=False)
    if ok:
      self.ui.menuCommands.removeAction(item_list[name_list.index(delitem)])
      del_user_macro(str(delitem))

  def changeFilelistFilters(self):
    ffilters=str(self.ui.filterEntry.text())
    self.ui.filenameList.changeFilters(list(map(str.strip, ffilters.split(';'))))
    cfg.set('gui', 'data file filters', ';'.join(self.ui.filenameList.filters))
    write_config()

  def openSearchDialog(self):
    dia=SearchDialog(self.ui.editor)
    dia.show()

  def openPrintDialog(self):
    printer=Qsci.QsciPrinter()
    printer.setWrapMode(Qsci.QsciScintilla.WrapWord)
    dia=QPrintDialog(printer, self)
    if  dia.exec_()==QPrintDialog.Accepted:
      printer.setDocName(self.openFile or '')
      printer.printRange(self.ui.editor)


  def toggleWrapMode(self):
    if self.ui.actionWrap_Lines.isChecked():
      self.ui.editor.setWrapMode(Qsci.QsciScintilla.WrapWord)
    else:
      self.ui.editor.setWrapMode(Qsci.QsciScintilla.WrapNone)

  ####################################

  def closeEvent(self, event=None):
    self._checkSave()
    settings=QSettings("AGlavic", "GnuplotEditor")
    settings.setValue("geometry", self.saveGeometry())
    settings.setValue("windowState", self.saveState())
    QMainWindow.closeEvent(self, event)
    if sys.version_info[0]>=3:
      cfg.set('gui', 'data file filters', ';'.join(self.ui.filenameList.filters))
    else:
      cfg.set('gui', 'data file filters', ';'.join(self.ui.filenameList.filters).encode('utf8'))
    write_config()

  def readSettings(self, event=None):
    settings=QSettings("AGlavic", "GnuplotEditor")
    if sys.version_info[0]>=3:
      ffilters=cfg.get('gui', 'data file filters')
      try:
        self.restoreGeometry(settings.value("geometry"))
        self.restoreState(settings.value("windowState"))
      except TypeError:
        pass
    else:
      self.restoreGeometry(settings.value("geometry"))
      self.restoreState(settings.value("windowState"))
      ffilters=cfg.get('gui', 'data file filters').decode('utf8')
    self.ui.filterEntry.setText(ffilters)
    self.ui.filenameList.changeFilters(list(map(str.strip, ffilters.split(';'))))


##############################################################################################
##############################################################################################

def run(args):
  app=QApplication(args)
  w=MainWindow()
  w.show()
  if len(args)>0 and not args[0].startswith('-'):
    w.fileOpen(args[0])
  return app.exec_()
