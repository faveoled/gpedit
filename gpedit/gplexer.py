#-*- coding: utf-8 -*-
'''
QScintilla Lexer for gnuplot input files.
'''
from PyQt5 import Qsci
from PyQt5.QtGui import QColor, QFont

_gp_keywords=['cd', 'call', 'clear', 'exit', 'fit', 'help', 'history', 'if', 'load',
              'pause', 'plot', 'using', 'with', 'index', 'every', 'smooth', 'thru', 'print',
              'pwd', 'quit', 'replot', 'reread', 'reset', 'save', 'set', 'show', 'unset',
              'shell', 'splot', 'system', 'test', 'unset', 'update']
_gp_funcs=[ 'abs', 'acos', 'acosh', 'arg', 'asin', 'asinh', 'atan', 'atan2', 'atanh',
            'besj0', 'besj1', 'besy0', 'besy1', 'ceil', 'cos', 'cosh', 'erf', 'erfc',
            'exp', 'floor', 'gamma', 'ibeta', 'inverf', 'igamma', 'imag', 'invnorm',
            'int', 'lambertw', 'lgamma', 'log', 'log10', 'norm', 'rand', 'real', 'sgn',
            'sin', 'sinh', 'sqrt', 'tan', 'tanh', 'column', 'defined', 'tm_hour',
            'tm_mday', 'tm_min', 'tm_mon', 'tm_sec', 'tm_wday', 'tm_yday', 'tm_year',
            'valid']
_gp_vars=[  'angles', 'arrow', 'autoscale', 'bars', 'bmargin', 'border', 'boxwidth',
            'clabel', 'clip', 'cntrparam', 'colorbox', 'contour', 'datafile ',
            'decimalsign', 'dgrid3d', 'dummy', 'encoding', 'fit', 'fontpath', 'format',
            'functions', 'function', 'grid', 'hidden3d', 'historysize', 'isosamples',
            'key', 'label', 'lmargin', 'loadpath', 'locale', 'logscale', 'mapping',
            'margin', 'mouse', 'multiplot', 'mx2tics', 'mxtics', 'my2tics', 'mytics',
            'mztics', 'offsets', 'origin', 'output', 'parametric', 'plot', 'pm3d',
            'palette', 'pointsize', 'polar', 'print', 'rmargin', 'rrange', 'samples',
            'size', 'style', 'surface', 'terminal', 'tics', 'ticslevel', 'ticscale',
            'timestamp', 'timefmt', 'title', 'tmargin', 'trange', 'urange', 'variables',
            'version', 'view', 'vrange', 'x2data', 'x2dtics', 'x2label', 'x2mtics',
            'x2range', 'x2tics', 'x2zeroaxis', 'xdata', 'xdtics', 'xlabel', 'xmtics',
            'xrange', 'xtics', 'xzeroaxis', 'y2data', 'y2dtics', 'y2label', 'y2mtics',
            'y2range', 'y2tics', 'y2zeroaxis', 'ydata', 'ydtics', 'ylabel', 'ymtics',
            'yrange', 'ytics', 'yzeroaxis', 'zdata', 'zdtics', 'cbdata', 'cbdtics',
            'zero', 'zeroaxis', 'zlabel', 'zmtics', 'zrange', 'ztics', 'cblabel',
            'cbmtics', 'cbrange', 'cbtics', 'term', 'terminal', 'output', 'font',
            'enhanced', 'x', 'y', 'z']
_gp_values=[
            ]
_gp_terminals=['pngcairo', 'png', 'x11', 'qt', 'wxt', 'pdf',
               'postscript', 'pdfcairo', 'pscairo', 'eps']

def setLexer(ed):
  '''
  :param Qsci.QsciScintilla ed:
  '''
  lexer=Qsci.QsciLexerPython()
  font=QFont('monospace', 10, QFont.Normal)
  lexer.setFont(font)
  lexer.setPaper(QColor(255, 255, 255),-1)
  #lexer.setColor(QColor(200, 0, 0), lexer.Keyword)

  ed.setLexer(lexer)
  ed.SendScintilla(ed.SCI_SETKEYWORDS, 0,
           ' '.join(_gp_values+_gp_keywords+_gp_funcs+_gp_vars+_gp_terminals).encode('utf8'))

  # enable autocompletion from the document
  ed.setAutoCompletionSource(ed.AcsDocument)
  ed.setAutoCompletionThreshold(2)
