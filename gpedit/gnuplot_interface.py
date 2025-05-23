#-*- coding: utf-8 -*-
'''
QThread that interacts with gnuplot directly to execute the scripts.
This is needed in oder not to block the editor when the script is running.
'''

import os
from subprocess import Popen, PIPE, STDOUT
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from threading import Event
import traceback
try:
  import win32process
except ImportError:
  win32process=None

class GnuplotInterface(QThread):
  _doShutdown=False
  scriptFinished=pyqtSignal()
  imagesFinished=pyqtSignal(int)
  mousePicked=pyqtSignal(float, float)
  lineExecuted=pyqtSignal(bool, str, int)
  lineSend=pyqtSignal(str, int)
  TERMINALS={
           'order': ['windows', 'qt', 'wxt', 'x11', 'aqua'],
           'windows': 'set term wxt %(n)i %(enhanced)s %(size)s %(font)s %(close)s %(title)s noraise',
           'aqua': 'set term aqua %(n)i %(enhanced)s %(size)s %(font)s %(title)s',
           'qt': 'set term qt %(n)i %(enhanced)s %(size)s %(font)s %(close)s %(title)s',
           'x11': 'set term x11 %(n)i %(enhanced)s %(size)s %(font)s %(close)s %(title)s',
           'wxt': 'set term wxt %(n)i %(enhanced)s %(size)s %(font)s %(close)s %(title)s',
           }
  encoding='utf8'

  def __init__(self, parent):
    QThread.__init__(self)
    self.parent=parent
    self.script=[]
    self.scriptIdle=Event()
    self.scriptIdle.set()
    self.shutdownScript=Event()
    self.shutdownScript.clear()
    self.shutdown=Event()
    self.shutdown.clear()
    self.initGnuplot()
  
  def run(self):
    while not self.shutdown.isSet():
      try:
        self._run()
      except IOError:
        self.initGnuplot()
      except:
        traceback.print_exc()
  
  def _run(self):
    while not self.shutdown.isSet():
      if len(self.script)>0:
        self.scriptIdle.clear()
        self.executeLine()
      else:
        self.scriptIdle.set()
        self.shutdown.wait(0.1)

  def initGnuplot(self):
    self.term_options=dict(self.parent._default_term_options)
    extra_opts={"bufsize": 0}
    gp_executable='gnuplot'
    if win32process is not None:
      extra_opts['creationflags']=win32process.CREATE_NO_WINDOW
      gp_executable=os.path.join(os.path.dirname(__file__), '..', 'gnuplot', 'gnuplot.exe')
    try: # if gnuplot is not in path, try typical folders (py2app doesn't work otherwise)
      self.gp=Popen(gp_executable, stdin=PIPE, stdout=PIPE, stderr=STDOUT, **extra_opts)
    except OSError:
      try:
        self.gp=Popen('/usr/bin/gnuplot', stdin=PIPE, stdout=PIPE, stderr=STDOUT, **extra_opts)
      except OSError:
        self.gp=Popen('/usr/local/bin/gnuplot', stdin=PIPE, stdout=PIPE, stderr=STDOUT, **extra_opts)
    # get available terminals
    self._write('print GPVAL_TERMINALS\n')
    self._write('print "====Command End===="\n')
    outstr=''
    while not outstr.endswith('====Command End===='):
      outstr+=str(self.gp.stdout.read(1), 'ascii', 'replace')
    outstr=outstr.split('====Command End====')[0].strip()
    terms=outstr.split()
    for term in self.TERMINALS['order']:
      if term in terms:
        self.parent.preview_term=self.TERMINALS[term]
        break
    self.write(self.parent.preview_term%dict(list(self.parent._default_term_options.items())+
                                        [('n', 1), ]))

  @pyqtSlot()
  def clear(self):
    self.scriptIdle.wait()
    self.write('unset output')
    self.write('reset')

  @pyqtSlot(str, int)
  @pyqtSlot(str)
  def write(self, line, lno=-1):
    self.script.append((line, lno))

  def _write(self, line):
    self.gp.stdin.write(line.encode(self.encoding))

  @pyqtSlot()
  def stopScript(self):
    self.shutdownScript.clear()
    self._doShutdown=True
    self.gp.terminate()
    self.shutdownScript.wait()

  def executeLine(self):
    next_item=self.script.pop(0)
    if isinstance(next_item, str):
      return getattr(self, '_'+next_item)()
    else:
      line, lno=next_item
    if line is None:
      if lno>0:
        self.imagesFinished.emit(lno)
      self.scriptFinished.emit()
      return
    self._write(line+'\n')
    if lno>=0:
      self.lineSend.emit(('[% 3i] '%lno)+line.replace('\n', '\n      ')+'\n', lno)
    else:
      self.lineSend.emit('gnuplot> '+line+'\n', lno)
    self._write('print "====Command End===="\n')
    outstr=''.encode(self.encoding) # trick to get a python3 byte string
    while not outstr.endswith('====Command End===='.encode(self.encoding)):
      if self.gp.poll() is not None:
        if self._doShutdown:
          self.script=[]
          self.shutdownScript.set()
          self._doShutdown=False
          self.lineExecuted.emit(True, outstr.strip().decode(self.encoding, 'replace')+'\n\n'+
                'Gnuplot killed during script execution, restarting...',-1)
          return
        self.lineExecuted.emit(False, outstr.strip().decode(self.encoding, 'replace')+'\n\n'+
                'Gnuplot process has been terminated unexpectedly, restarting...', lno)
        self.initGnuplot()
        raise RuntimeError('Gnuplot terminated')
      next_byte=self.gp.stdout.read(1)
      outstr+=next_byte
    outstr=outstr.decode(self.encoding, 'replace').split('====Command End====')[0].strip()
    err='gnuplot>' in outstr
    if lno>=0:
      outstr=outstr.replace('line 0:', '').replace('gnuplot>', 'line %i:'%lno)
    outstr=outstr.strip()
    self.lineExecuted.emit(not err, outstr, lno)

  def pickPosition(self):
    self.script.append('pickPosition')
  
  def _pickPosition(self):
    self._write('pause mouse\n')
    self._write('print "x=",MOUSE_X\n')
    self._write('print "y=",MOUSE_Y\n')
    self._write('print "====Command End===="\n')
    outstr=''.encode(self.encoding) # trick to get a python3 byte string
    while not outstr.endswith('====Command End===='.encode(self.encoding)):
      if self.gp.poll() is not None:
        if self._doShutdown:
          self.script=[]
          self.shutdownScript.set()
          self._doShutdown=False
          self.lineExecuted.emit(True, outstr.strip().decode(self.encoding, 'replace')+'\n\n'+
                'Gnuplot killed during script execution, restarting...',-1)
          return
        self.lineExecuted.emit(False, outstr.strip().decode(self.encoding, 'replace')+'\n\n'+
                'Gnuplot process has been terminated unexpectedly, restarting...',-1)
        self.initGnuplot()
        raise RuntimeError('Gnuplot terminated')
      next_byte=self.gp.stdout.read(1)
      outstr+=next_byte
    outstr=outstr.decode(self.encoding, 'replace').split('====Command End====')[0].strip()
    try:
      x=float(outstr.split('x=')[1].splitlines()[0])
    except ValueError:
      x=0.
    try:
      y=float(outstr.split('y=')[1].splitlines()[0])
    except ValueError:
      y=0.
    err='gnuplot>' in outstr
    self.lineExecuted.emit(not err, outstr,-1)
    self.mousePicked.emit(x, y)
