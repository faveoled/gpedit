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
from PyQt5.QtCore import Qt, QUrl, QSettings, pyqtSlot, QFileSystemWatcher # pyqtSlot is here
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
  fileChanged=False # This will be driven by editor's modificationChanged signal
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
    self.gpi.processCrashed.connect(self.handleGnuplotCrash) # New signal connection
    self.gpi.start()

    self.readSettings()
    # Connect editor's modificationChanged signal to textModified slot
    self.ui.editor.modificationChanged.connect(self.textModified)
    # Initialize window title
    self.textModified(False)


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
      pass # Older QScintilla might not have this
    ed.setWrapIndentMode(Qsci.QsciScintilla.WrapIndentFixed)

    # Margin 0 is used for line numbers
    font=QFont('Sans', 10, QFont.Normal)
    fontmetrics=QFontMetrics(font)
    ed.setMarginsFont(font)
    ed.setMarginWidth(0, fontmetrics.width("0000")+6) # Increased width for 4-digit lines
    ed.setMarginLineNumbers(0, True)
    ed.setMarginsBackgroundColor(QColor("#cccccc"))

    # behavior of marginc area
    ed.setMarginSensitivity(1, True)
    ed.marginClicked.connect(self.detectorMarginClicked)
    self.ignore_marker=ed.markerDefine(Qsci.QsciScintilla.RightTriangle)
    ed.setMarkerBackgroundColor(QColor("#eeee11"), self.ignore_marker)
    self.error_marker=ed.markerDefine(Qsci.QsciScintilla.Rectangle) # Changed from SC_MARK_RECTANGLE for clarity
    ed.setMarkerBackgroundColor(QColor("#ee1111"), self.error_marker)

    setLexer(ed)

  def buildMenus(self):
    self.action_macros={}
    action=QAction('encoding', self.ui.menuSet)
    action.triggered.connect(self.insertEncoding)
    self.ui.menuSet.addAction(action)
    self._addMenuEntries(self.ui.menuSet, SET_ACTIONS)
    self._addMenuEntries(self.ui.menuPalette, PALETTS)
    # User macros menu will be cleared and rebuilt if macros change
    self.ui.menuCommands.clear() 
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
      
      # Ensure label and item are strings
      if not isinstance(label, str): label = str(label)
      if not isinstance(item, str) and not isinstance(item, list): item = str(item)

      if isinstance(item, str):
        if icon:
          action=QAction(icon, label, menu)
        else:
          action=QAction(label, menu)
        action.triggered.connect(self.insertMacro)
        self.action_macros[action]=item
        menu.addAction(action)
      else: # This means item is a list for a submenu
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
    ed.setCursorPosition(l+1, c) # Move cursor to next line

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
    if lno>=0 and not result: # lno is 1-based from gnuplot_interface
      self.ui.editor.markerAdd(lno-1, self.error_marker) # editor lines are 0-based

  @pyqtSlot()
  def gnuplotScriptFinished(self):
    if self._images_waiting is None: # Only reset if not waiting for images
      self.ui.plotImage.setText('Run Script')
      self._scriptRunning=False

  # New slot to handle Gnuplot process crashes
  @pyqtSlot()
  def handleGnuplotCrash(self):
      self.ui.gnuplotOutput.insertPlainText("Gnuplot process terminated unexpectedly or crashed. Re-initializing Gnuplot interface.\n")
      self.ui.plotImage.setText('Run Script')
      self._scriptRunning = False
      self._images_waiting = None # Clear any pending image expectations
      # The GnuplotInterface is responsible for its own re-initialization (initGnuplot)
      # and clearing its internal script queue.
      # MainWindow just needs to reset its own state.
      # Ensure GnuplotInterface's scriptIdle is set if its queue is empty.
      if self.gpi is not None and not self.gpi.script: # Check if interface's script queue is empty
          if not self.gpi.scriptIdle.is_set():
               self.gpi.scriptIdle.set()

  def analyzeScript(self):
    ed=self.ui.editor
    txt=str(self.ui.editor.text())
    txt_lines=list(map(str.strip, txt.splitlines()))
    # removed marked lines
    line_idx=list(range(len(txt_lines))) # Keep original line numbers (0-based)
    i=0
    while i<len(txt_lines):
      # Skip empty or comment lines for processing, but keep original line numbers
      if txt_lines[i] == '' or txt_lines[i].strip().startswith('#'):
        txt_lines.pop(i)
        line_idx.pop(i)
        continue
      
      # Join lines ended with \\ as one command
      # Ensure to handle the case where the last line ends with \
      current_command = txt_lines[i]
      while current_command.strip().endswith('\\'):
        txt_lines.pop(i) # Remove current line part
        original_line_num_of_current_part = line_idx.pop(i) # Remove its original number
        if i < len(txt_lines): # If there's a next line
            current_command = current_command.strip().rstrip('\\') + '\n' + txt_lines[i]
            # The combined command now corresponds to the original line number of its first part
            # The line number of the next part (now part of current_command) is effectively removed
        else: # Last line ends with '\', just strip it
            current_command = current_command.strip().rstrip('\\')
            break # No more lines to join
      txt_lines[i] = current_command # Update the line in txt_lines
      
      # Handle ignored lines based on editor markers
      # line_idx[i] is the original 0-based line number
      if ed.markersAtLine(line_idx[i]) & (1 << self.ignore_marker):
        txt_lines.pop(i)
        line_idx.pop(i)
        continue

      # join data after a plot "-" into one command
      # This logic needs to be careful with line_idx if lines are merged
      strip_line = txt_lines[i].strip()
      if strip_line.startswith('plot "-"') or \
         strip_line.startswith("plot '-'") or \
         strip_line.startswith('splot "-"') or \
         strip_line.startswith("splot '-'"):
        
        original_plot_line_num = line_idx[i] # Save original line number of plot command
        # Start accumulating data lines
        data_block = []
        # Remove the plot command itself from processing list for now, will re-add combined command
        current_plot_command = txt_lines.pop(i)
        line_idx.pop(i)

        while i < len(txt_lines):
            data_line = txt_lines[i]
            if data_line.strip().lower() == 'e': # End of data block
                txt_lines.pop(i) # Remove 'e'
                line_idx.pop(i) # Remove 'e's line number
                break
            else:
                data_block.append(data_line)
                txt_lines.pop(i) # Remove data line from list
                line_idx.pop(i) # Remove its line number
        
        # Combine plot command with its data block
        combined_command = current_plot_command + '\n' + '\n'.join(data_block) + '\ne'
        # Insert the combined command back at the current position 'i'
        txt_lines.insert(i, combined_command)
        line_idx.insert(i, original_plot_line_num) # Associate with original plot line number
      i+=1
    return line_idx, txt_lines


  @pyqtSlot()
  @pyqtSlot(bool)
  def evaluateScript(self, force=True, reset_after=True):
    if self._scriptRunning:
      self.gpi.stopScript() # stopScript should handle UI/state changes via signals
      return
    ed=self.ui.editor
    line_idx, txt_lines=self.analyzeScript()
    
    if not txt_lines: # Check if there are any lines to execute
        if self._scriptRunning: # Should not happen if stopScript works
             self.ui.plotImage.setText('Run Script')
             self._scriptRunning=False
        return

    if (self.last_script==txt_lines and not force):
      return
    
    for i in range(ed.lines()): # Clear previous error markers
      ed.markerDelete(i, self.error_marker)

    self._images_waiting=None
    self._scriptRunning=True
    self.ui.plotImage.setText('Stop Run')
    self.last_script=txt_lines
    self.gpi.clear() # Clear gnuplot state
    self.ui.gnuplotInput.clear(); self.ui.gnuplotOutput.clear()

    self.window_idx=1 # Reset plot window counter
    for i, line_content in enumerate(txt_lines):
      original_line_number = line_idx[i] # 0-based original line number
      
      # analyzeLine might modify self.window_idx
      # checkIgnore is related to 'set output' and 'set term' which might affect window_idx
      if self.checkIgnore(line_content): 
        self.analyzeLine(line_content) # Pass content, not original line number
        continue
      
      if line_content.strip().startswith('load'):
        try:
          self.analyzeLoad(line_content) # Pass content
        except Exception as e:
          self.ui.gnuplotOutput.insertPlainText(f"Error processing load command on line {original_line_number+1}: {e}\n")
          ed.markerAdd(original_line_number, self.error_marker)

      # Send to gnuplot interface with 1-based line number for display/error reporting
      self.gpi.write(line_content, original_line_number + 1) 

    # Close any extra plot windows that were opened in previous runs but not this one
    for i in range(self.window_idx, self.n_terms+1):
      # Construct term options for closing window 'i'
      close_opts = dict(self._default_term_options)
      close_opts.update({'n': i, 'close': 'close'})
      self.gpi.write(self.preview_term % close_opts)
    
    self.n_terms = self.window_idx - 1 # Update number of active terms for next run

    if reset_after:
      self.gpi.write(None,-1) # Indicate that script ends here


  def analyzeLoad(self, srcline_content): # Takes content of the load line
    name_part = srcline_content.strip().split(None, 1)[1].strip()
    # Basic parsing for quoted filename
    if (name_part.startswith('"') and name_part.endswith('"')) or \
       (name_part.startswith("'") and name_part.endswith("'")):
        name = name_part[1:-1]
    else: # Unquoted filename (less common but possible)
        name = name_part

    # Resolve relative paths based on current script's directory if a script is open
    if self.openFile:
        base_dir = os.path.dirname(self.openFile)
        name = os.path.join(base_dir, name)
    
    if not os.path.exists(name):
        self.ui.gnuplotOutput.insertPlainText(f"Load file not found: {name}\n")
        # Optionally mark the load line with an error
        return

    try:
        with open(name, 'r', encoding=self.ui.encoding.currentText()) as f: # Use selected encoding
            loaded_txt = f.read()
        
        # Process lines from the loaded file.
        # This is a simplified version; real gnuplot 'load' can be complex.
        # For now, just analyze lines for 'set term' and 'set output' like in main script.
        for line in loaded_txt.splitlines():
            line_strip = line.strip()
            if line_strip.startswith('load'):
                self.analyzeLoad(line) # Recursive load
            elif self.checkIgnore(line_strip): # checkIgnore looks for 'set term', 'set output'
                self.analyzeLine(line_strip) # analyzeLine updates window_idx
            # Note: Loaded script lines are not directly sent to gpi.write here.
            # The original load command is sent by evaluateScript. Gnuplot handles the actual loading.
            # This analyzeLoad is primarily for tracking window_idx for our preview.
    except Exception as e:
        self.ui.gnuplotOutput.insertPlainText(f"Error reading or processing loaded file {name}: {e}\n")


  def analyzeLine(self, line_content): # Takes content of the line
    line_strip = line_content.strip()
    if line_strip.startswith('set'):
      sopts = line_strip.split('set ', 1)[1].strip()
      if sopts.startswith('term'):
        self.analyzeTerm(line_content) # Pass full line content
      # Check for 'set output' that defines a filename (and thus implies a new plot window for preview)
      if sopts.startswith('output') and ('"' in sopts or "'" in sopts):
        # This line means gnuplot is plotting to a file.
        # For preview purposes, we tell gpi to also plot to a preview window.
        # Update term_options if necessary (e.g., if 'set term' was just processed)
        current_term_opts = dict(self.term_options) # Use current term options
        current_term_opts['n'] = self.window_idx # Set current window number
        # Ensure 'close' is not in term_options for this preview window unless it's the last one
        if 'close' in current_term_opts: del current_term_opts['close']

        self.gpi.write(self.preview_term % current_term_opts)
        
        if self.ui.applySize.isChecked(): sleep(0.1) # Wait for window to be resized (if applicable)
        self.window_idx += 1


  @pyqtSlot()
  def evaluateScriptImage(self):
    if self._scriptRunning:
      self.gpi.stopScript() # stopScript should handle UI/state reset
      return
      
    ed=self.ui.editor
    line_idx, txt_lines=self.analyzeScript()

    if not txt_lines: # No executable lines
        return

    for i in range(ed.lines()): # Clear previous error markers
      ed.markerDelete(i, self.error_marker)
      
    self._scriptRunning=True
    self.ui.plotImage.setText('Stop Run')
    self.gpi.clear() # Clear gnuplot state
    self.ui.gnuplotInput.clear(); self.ui.gnuplotOutput.clear()

    fnames=[]
    for i, line_content in enumerate(txt_lines):
      original_line_number = line_idx[i] # 0-based original line number
      line_strip = line_content.strip()

      if line_strip.startswith('set') and 'output' in line_strip:
        if not ('"' in line_strip or "'" in line_strip): # Skip if no filename
          continue
        
        # Extract filename
        parts = line_strip.split()
        fn = None
        for part in parts:
            if part.startswith('"') and part.endswith('"'):
                fn = part[1:-1]
                break
            if part.startswith("'") and part.endswith("'"):
                fn = part[1:-1]
                break
        if fn:
            # Make filename absolute if script is saved, otherwise relative to CWD
            if self.openFile:
                fn = os.path.join(os.path.dirname(self.openFile), fn)
            else:
                fn = os.path.abspath(fn)
            fnames.append(fn)
            
      self.gpi.write(line_content, original_line_number + 1) # Send with 1-based line number

    self.gpi.write('unset output') # Ensure output is unset after all commands
    self.gpi.write(None, len(fnames)) # Indicate script ends, pass count of expected images
    self._images_waiting=fnames


  def checkIgnore(self, line_content): # Takes line content
    line_strip = line_content.strip()
    if line_strip.startswith('set '):
      sopts=line_strip.split('set ', 1)[1].strip()
      if sopts.startswith('output'): # 'set output' itself is not ignored for sending, but its analysis is special
        return True 
      elif sopts.startswith('term'): # 'set term' is also not ignored, but analyzed
        return True
    return False


  def analyzeTerm(self, line_content): # Takes line content
    line_no_comment = line_content.split('#')[0].strip() # Remove comments
    
    # Reset term_options to defaults before parsing the new 'set term' line
    self.term_options = dict(self._default_term_options)
    
    # Example: 'set term pdfcairo enhanced font "Arial,10" size 5in,3in'
    parts = line_no_comment.lower().split() # Process in lowercase for easier matching

    if 'noenhanced' in parts:
      self.term_options['enhanced']='noenhanced'
    elif 'enhanced' in parts: # Check for 'enhanced' explicitly
      self.term_options['enhanced']='enhanced'

    # Font parsing needs to be careful with quoted strings
    if self.ui.applyFont.isChecked() and 'font' in line_no_comment: # Use original line for font parsing
        try:
            font_idx = line_no_comment.lower().index('font')
            font_spec_part = line_no_comment[font_idx + len('font'):].strip()
            
            quote_char = None
            if font_spec_part.startswith('"'): quote_char = '"'
            elif font_spec_part.startswith("'"): quote_char = "'"

            if quote_char:
                end_quote_idx = font_spec_part.find(quote_char, 1)
                if end_quote_idx != -1:
                    font_str = font_spec_part[1:end_quote_idx]
                    font_name, *font_size_parts = font_str.split(',')
                    if font_name: self.term_options['font_name'] = font_name.strip()
                    if font_size_parts and font_size_parts[0].strip().isdigit():
                         self.term_options['font_size'] = int(font_size_parts[0].strip())
        except ValueError: # font not found or format error
            pass # Keep default font

    # Size parsing
    if self.ui.applySize.isChecked() and 'size' in line_no_comment: # Use original line for size
        try:
            size_idx = line_no_comment.lower().index('size')
            size_spec_part = line_no_comment[size_idx + len('size'):].strip()
            # Example: "5in,3in" or "1024,768"
            # This is a simplified parser. Gnuplot 'size' can have units (in, cm, px).
            # We are mostly interested in pixel dimensions for preview.
            # If units are present, conversion would be needed. For now, assume pixel values or direct numbers.
            
            size_parts_str = size_spec_part.split()[0] # Take the first part after 'size'
            w_str, h_str = size_parts_str.split(',')
            
            # Basic extraction, removing units for simplicity for now
            w = float("".join(filter(str.isdigit or str.isspace or str.__eq__=='.', w_str)))
            h = float("".join(filter(str.isdigit or str.isspace or str.__eq__=='.', h_str)))

            size_multiply=[1., 0.5, 0.25][self.ui.sizeMultiply.currentIndex()]
            w *= size_multiply
            h *= size_multiply
            self.term_options['size'] = f'size {int(w)},{int(h)}'

        except ValueError: # size not found or format error
            pass # Keep default size

    # Update the main preview_term string based on parsed options for the next plot
    # This is a bit tricky as self.preview_term is a format string like 'set term wxt ...'
    # We need to replace parts of it or rebuild it.
    # For simplicity, let's assume self.preview_term is for 'wxt' or 'qt' and mainly update font/size.
    # The actual 'set term' line sent to gnuplot is the one from the script.
    # This analysis is for matching preview window behavior.
    
    # Update the font part of term_options for the preview formatter
    font_name = self.term_options.get('font_name', 'Arial') # Default if not parsed
    font_size = self.term_options.get('font_size', 14)      # Default if not parsed
    self.term_options['font'] = f'font "{font_name},{font_size}"'
    # Size is already in 'size W,H' format if parsed, or default empty string


  def clearImages(self):
    # Check if layout exists before trying to manipulate it
    if self.ui.gnuplotImageHolder.layout() is not None:
        vbox = self.ui.gnuplotImageHolder.layout()
        while vbox.count(): # Safely remove items
            item = vbox.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater() # Use deleteLater for safety with Qt event loop
    else: # If no layout, create one (should have been created by .ui file)
        vbox = QVBoxLayout(self.ui.gnuplotImageHolder)
        self.ui.gnuplotImageHolder.setLayout(vbox)


  @pyqtSlot()
  def showImages(self): # This slot is connected to gpi.imagesFinished
    self.ui.plotImage.setText('Run Script') # Reset button text
    self._scriptRunning=False # Reset running state
    
    if self._images_waiting is None: # Should not happen if logic is correct
        return

    fnames=self._images_waiting
    self._images_waiting = None # Clear the waiting list once processed

    self.plotimage_pixmaps=[]
    self.plotimage_labels=[]
    
    widget=self.ui.gnuplotImageHolder
    # Ensure there's a layout, create if not (though it should exist from UI setup)
    if widget.layout() is None:
        vbox_layout = QVBoxLayout(widget)
        widget.setLayout(vbox_layout)
    else:
        vbox_layout = widget.layout()

    self.clearImages() # Clear previous images from the layout

    ftxt_parts=[]
    for fname in fnames:
      # fname should be absolute path from evaluateScriptImage
      if not os.path.exists(fname):
        self.ui.gnuplotOutput.insertPlainText(f"Image file not found: {fname}\n")
        continue
      
      ftxt_parts.append(fname)
      label=QLabel(widget) # Parent to gnuplotImageHolder
      vbox_layout.addWidget(label) # Add to layout

      pixmap = None
      try:
          if fname.lower().endswith('.pdf'):
            if popplerqt5 is None:
              label.setText("Can't display PDF: popplerqt5 library not found.")
            else:
              doc=popplerqt5.Poppler.Document.load(fname)
              if doc and doc.numPages() > 0:
                  # Render at a reasonable DPI for screen display
                  img=doc.page(0).renderToImage(150., 150.) 
                  pixmap=QPixmap.fromImage(img)
              else:
                  label.setText(f"Could not load or empty PDF: {os.path.basename(fname)}")
          elif fname.lower().endswith('.svg'):
            renderer=QSvgRenderer(fname)
            if renderer.isValid():
                # Create a QPixmap with the default size of the SVG
                # If SVG has no size, it might be small, consider setting a default/min size
                default_size = renderer.defaultSize()
                if default_size.width() < 100 or default_size.height() < 100: # Example minimum
                    # Heuristic: scale up small SVGs for better preview, or use a fixed size
                    target_width = max(default_size.width(), 300) # at least 300px wide
                    target_height = (target_width / default_size.width()) * default_size.height() if default_size.width() > 0 else 300
                    pixmap_size = QSize(int(target_width), int(target_height))
                else:
                    pixmap_size = default_size

                pixmap_img = QPixmap(pixmap_size)
                pixmap_img.fill(Qt.transparent) # Fill with transparent background
                painter=QPainter(pixmap_img)
                renderer.render(painter)
                painter.end() # Crucial to end painting
                pixmap = pixmap_img
            else:
                label.setText(f"Could not render SVG: {os.path.basename(fname)}")
          else: # Attempt to load as other common image formats (PNG, JPG, etc.)
            pixmap=QPixmap(fname)
            if pixmap.isNull(): # Check if pixmap loading failed
                label.setText(f"Unsupported image format or error loading: {os.path.basename(fname)}")
                pixmap = None # Ensure it's None if failed
      except Exception as e:
          label.setText(f"Error loading image {os.path.basename(fname)}: {e}")
          pixmap = None

      self.plotimage_pixmaps.append(pixmap) # Append pixmap or None
      self.plotimage_labels.append(label) # Append label for later updates

    self.ui.fileName.setText('; '.join(ftxt_parts)) # Display all processed filenames
    self.displayPixmaps() # Scale and show loaded pixmaps


  def displayPixmaps(self):
    if self.plotimage_pixmaps is None or not self.plotimage_labels:
      return

    scroll_area_width = self.ui.gnuplotImageScroller.width() - 20 # Approx scrollbar width
    scroll_area_height = self.ui.gnuplotImageScroller.height() - 20

    for i, pixmap_orig in enumerate(self.plotimage_pixmaps):
      label = self.plotimage_labels[i]
      if pixmap_orig is None or pixmap_orig.isNull():
        # Label might already have error text from showImages
        if not label.text(): label.setText("Image not available")
        label.adjustSize() # Adjust label size to text
        continue

      w_orig, h_orig = pixmap_orig.width(), pixmap_orig.height()
      if w_orig == 0 or h_orig == 0:
          label.setText("Invalid image dimensions (0x0)")
          continue

      current_scale = 1.0
      if self.ui.scaleToFit.isChecked():
        if w_orig > scroll_area_width or h_orig > scroll_area_height : # Only scale down if larger
            scale_w = scroll_area_width / w_orig
            scale_h = scroll_area_height / h_orig
            current_scale = min(scale_w, scale_h)
      else:
        try:
          current_scale=float(self.ui.scaling.text())/100.
        except ValueError:
          current_scale=1.0 # Default to 100% if input is invalid

      w_scaled = int(w_orig * current_scale)
      h_scaled = int(h_orig * current_scale)

      if w_scaled > 0 and h_scaled > 0:
          pix_scaled = pixmap_orig.scaled(w_scaled, h_scaled,
                                        Qt.KeepAspectRatio, # Keep aspect ratio
                                        Qt.SmoothTransformation)
          label.setPixmap(pix_scaled)
          label.setGeometry(0, 0, pix_scaled.width(), pix_scaled.height()) # Set geometry for the label itself
          label.setFixedSize(pix_scaled.width(), pix_scaled.height()) # Ensure label is sized to pixmap
      else: # Scaled to 0, don't show
          label.clear() 
          label.setText("Scaled to zero size")

      label.show()
    
    # Adjust the size of gnuplotImageHolder if its layout is managing multiple labels vertically
    # This ensures the scroll area's viewport is correctly sized.
    if self.ui.gnuplotImageHolder.layout() is not None:
        self.ui.gnuplotImageHolder.adjustSize()



  def detectorMarginClicked(self, nmarker, nline, modifiers):
    ed=self.ui.editor
    # Check if the specific ignore_marker is at the line
    # markersAtLine returns a bitmask. We need to check for our specific marker bit.
    marker_bit = (1 << self.ignore_marker) # Calculate the bit for our marker handle
    if ed.markersAtLine(nline) & marker_bit:
        ed.markerDelete(nline, self.ignore_marker)
    else: # No ignore_marker, add it (don't care about other markers)
        ed.markerAdd(nline, self.ignore_marker)
        
    if self.ui.autoPreview.isChecked() and not self._scriptRunning: # Avoid re-eval if script is already running
      self.evaluateScript()


  ################### Menu Actions #################
  def commentSelection(self):
    ed=self.ui.editor
    start_line, start_index, end_line, end_index = ed.getSelection()
    
    ed.beginUndoAction() # Group commenting into a single undo action
    # If selection spans multiple lines or no text is selected on a single line, comment whole lines
    if start_line != end_line or (start_line == end_line and start_index == end_index):
        for nline in range(start_line, end_line + 1):
            ed.insertAt("#", nline, 0)
    else: # Single line, partial selection: comment out the selection by wrapping it
        # This is more complex if we want to be clever.
        # Simple approach: just prepend # to the line.
        ed.insertAt("#", start_line, 0)
    ed.endUndoAction()

    if self.ui.autoPreview.isChecked() and not self._scriptRunning:
      self.evaluateScript()


  def uncommentSelection(self):
    ed=self.ui.editor
    start_line, _, end_line, _ = ed.getSelection() # We only need line numbers

    ed.beginUndoAction()
    for nline in range(start_line, end_line + 1):
        line_text = ed.text(nline)
        if line_text.lstrip().startswith('#'):
            # Remove the first '#' after leading whitespace
            hash_index = line_text.find('#')
            ed.delete(nline, hash_index, nline, hash_index + 1)
        elif line_text.startswith('#'): # No leading whitespace, starts with #
            ed.delete(nline, 0, nline, 1)
    ed.endUndoAction()

    if self.ui.autoPreview.isChecked() and not self._scriptRunning:
      self.evaluateScript()


  def ignoreSelection(self):
    ed=self.ui.editor
    start_line, _, end_line, _ = ed.getSelection()
    for nline in range(start_line, end_line + 1):
      ed.markerAdd(nline, self.ignore_marker)
    if self.ui.autoPreview.isChecked() and not self._scriptRunning:
      self.evaluateScript()

  def unignoreSelection(self):
    ed=self.ui.editor
    start_line, _, end_line, _ = ed.getSelection()
    for nline in range(start_line, end_line + 1):
      ed.markerDelete(nline, self.ignore_marker) # Delete specific marker
    if self.ui.autoPreview.isChecked() and not self._scriptRunning:
      self.evaluateScript()

  def pasteColor(self):
    color=QColorDialog.getColor(parent=self)
    if color.isValid(): # Check if a color was actually selected
        r, g, b, _a=color.getRgb()
        cstring='#%02x%02x%02x'%(r, g, b)
        self.ui.editor.insert(cstring)

  def pickPosition(self):
    # Evaluate script first to ensure plot is up-to-date, but don't reset/finish script in gpi
    self.evaluateScript(force=True, reset_after=False) 
    
    # Check if script evaluation started correctly
    if not self._scriptRunning:
        QMessageBox.warning(self, "Pick Position", "Could not start script evaluation for picking position.")
        return

    self.pickmsg=QDialog(self)
    self.pickmsg.setWindowTitle("Pick Position")
    vbox=QVBoxLayout(self.pickmsg)
    vbox.addWidget(QLabel('Click on the Gnuplot window to pick a position.\nThe coordinates will be inserted into the editor.', self.pickmsg))
    self.pickmsg.setModal(False) # Allow interaction with main window if needed, though focus is on gnuplot
    self.pickmsg.show()
    
    self.gpi.pickPosition() # Tell gnuplot_interface to expect a mouse click

  @pyqtSlot(float, float)
  def positionPicked(self, x, y):
    # This slot is called by gnuplot_interface when coordinates are received
    if hasattr(self, 'pickmsg') and self.pickmsg.isVisible():
        self.pickmsg.close()

    self.ui.plotImage.setText('Run Script') # Reset button after picking
    self._scriptRunning=False 
    self._images_waiting=None # Clear any image waiting state

    self.ui.editor.insert('%g,%g'%(x, y))
    self.activateWindow() # Bring main window to front
    self.ui.editor.setFocus() # Focus on editor


  def newDocument(self):
    if not self._checkSave(): return # If user cancels, do nothing
    self.openFile=None
    self.ui.editor.clear()
    self.ui.editor.setModified(False) 
    self.textModified(False) # Update window title via this slot
    self.clearImages() # Clear any displayed images


  @pyqtSlot()
  def insertTemplate(self):
    # Prioritize TEMP for Windows, then TMP, then default to /tmp for others
    temp_dir = os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp'
    # Ensure path separators are correct for gnuplot strings (double backslashes for Windows)
    gpl_temp_dir = temp_dir.replace('\\', '\\\\')
    template_text = TEMPLATE % gpl_temp_dir
    
    self.ui.editor.insert(template_text)
    if self.ui.autoPreview.isChecked() and not self._scriptRunning:
      self.evaluateScript(False)


  def changeEncoding(self, new_encoding_text): # Argument is the text from combobox
    current_text = self.ui.editor.text()
    # Try to find existing 'set encoding' line
    lines = current_text.splitlines()
    found_encoding_line = False
    for i, line in enumerate(lines):
        if line.strip().lower().startswith('set encoding'):
            # Preserve indentation/prefix before 'set encoding'
            prefix = line[:line.lower().find('set encoding')]
            lines[i] = prefix + 'set encoding ' + new_encoding_text
            found_encoding_line = True
            break
    
    if not found_encoding_line: # Add as a new line at the top
        lines.insert(0, 'set encoding ' + new_encoding_text)

    self.ui.editor.setText('\n'.join(lines))
    # No need to call evaluateScript, gnuplot handles encoding when it loads/runs.
    # However, if autoPreview is on, it might be desired. For now, assume manual re-run.


  def fileOpen(self, fname_arg=None): # Renamed fname to fname_arg to avoid conflict
    if not self._checkSave(): return

    file_to_open = fname_arg
    if not file_to_open:
      # Use current directory of openFile if available, else CWD
      start_dir = os.path.dirname(self.openFile) if self.openFile else os.path.abspath(os.curdir)
      file_to_open, _ = QFileDialog.getOpenFileName(self, 'Select Script to Open',
                                       start_dir,
                                       'Gnuplot Script (*.gp *.gpl *.txt);;All (*)')
      if not file_to_open: # Dialog cancelled
        return

    file_to_open=os.path.abspath(str(file_to_open))
    
    try:
        # Determine encoding: 1. from file content, 2. from current UI setting, 3. fallback (UTF-8)
        detected_encoding = None
        try: # Try to read a few lines to detect 'set encoding'
            with open(file_to_open, 'rb') as f_check:
                preview_bytes = f_check.read(1024) # Read first 1KB
            preview_text = preview_bytes.decode('ascii', 'ignore') # Decode as ASCII to find 'set encoding'
            for line_preview in preview_text.splitlines():
                if line_preview.strip().lower().startswith('set encoding'):
                    detected_encoding = line_preview.strip().split(None, 2)[-1].strip("'\"")
                    break
        except Exception:
            pass # Ignore errors in encoding detection for now

        final_encoding = detected_encoding or self.ui.encoding.currentText() or 'utf-8'
        
        # Update UI encoding selector if a different one was detected in file
        if detected_encoding:
            enc_idx = self.ui.encoding.findText(detected_encoding, Qt.MatchFixedString | Qt.MatchCaseSensitive)
            if enc_idx >= 0:
                self.ui.encoding.setCurrentIndex(enc_idx)
            else: # If detected encoding not in list, maybe add it or warn user
                print(f"Warning: File specified encoding '{detected_encoding}' not in standard list.")


        with open(file_to_open, 'r', encoding=final_encoding, errors='replace') as f:
            ftxt = f.read()
        
        self.openFile=file_to_open # Set after successful read
        fdir=os.path.dirname(file_to_open)
        self._changeDir(fdir) # Change CWD for gnuplot and file browser

        self.ui.editor.setText('') # Clear first to avoid flicker/append
        self.ui.editor.setText(ftxt)
        self.ui.editor.setModified(False)
        self.textModified(False) # Updates window title

        self.clearImages() # Clear any images from previous script
        if self.ui.autoPreview.isChecked() and not self._scriptRunning:
          self.evaluateScript()

    except Exception as e:
        QMessageBox.critical(self, "Error Opening File", f"Could not open or read file:\n{file_to_open}\n\nError: {e}")
        # Do not change self.openFile or window title on error
        return


  def fileSave(self):
    if not self.openFile: 
        self.fileSaveAs() # Behaves as Save As if no file is currently open
    else:
        self.fileSaveAs(self.openFile) # Saves to the current file


  def fileSaveAs(self, fname_arg=None): # Renamed fname to fname_arg
    file_to_save = fname_arg
    if not file_to_save:
      start_path = self.openFile if self.openFile else os.path.join(os.path.abspath(os.curdir), "untitled.gp")
      file_to_save, _ =QFileDialog.getSaveFileName(self, 'Save File As',
                                        start_path,
                                        'Gnuplot Script (*.gp *.gpl *.txt);;All (*)')
    if file_to_save: # Proceed if a filename was chosen (not cancelled)
      file_to_save=os.path.abspath(str(file_to_save))
      try:
          # Save with the encoding specified in the UI's encoding combobox
          encoding_to_save = self.ui.encoding.currentText() or 'utf-8' # Fallback to UTF-8
          with open(file_to_save, 'w', encoding=encoding_to_save, errors='replace') as f:
              f.write(self.ui.editor.text())
          
          self.openFile=file_to_save # Update current open file
          fdir=os.path.dirname(file_to_save)
          self._changeDir(fdir) # Update CWD
          self.ui.editor.setModified(False)
          self.textModified(False) # Update window title
      except Exception as e:
          QMessageBox.critical(self, "Error Saving File", f"Could not save file:\n{file_to_save}\n\nError: {e}")


  def _checkSave(self): # Returns True if safe to proceed, False if user cancelled
    if self.ui.editor.isModified(): 
      reply=QMessageBox.question(self, 'Save Changes',
                            'The current document has been modified. Do you want to save the changes?',
                            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, 
                            QMessageBox.Save) # Default to Save
      if reply == QMessageBox.Save:
        self.fileSave()
        # After saving, the document is no longer modified.
        # If fileSave was cancelled internally (e.g. user cancels Save As dialog),
        # isModified will still be true. So, re-check.
        return not self.ui.editor.isModified() 
      elif reply == QMessageBox.Cancel:
        return False # User cancelled, do not proceed with original action
      # If Discard, proceed without saving (isModified remains true until content changes or new file loaded)
    return True # Safe to proceed (no changes or user chose Discard)


  def _changeDir(self, fdir):
    try:
        os.chdir(fdir)
        # Basic quoting for cd command to handle spaces, etc.
        # Gnuplot's cd might need more robust quoting for complex paths.
        gpi_fdir = fdir.replace("'", "'\"'\"'") # Wraps single quotes: ' -> '"'"'
        self.gpi.write(f"cd '{gpi_fdir}'") 
        
        self.ui.filenameList.changeDirectory(fdir) # Update file browser view
        
        # Update path watcher
        if self._active_path and self._active_path != fdir:
            if os.path.exists(self._active_path): # Check if path still exists before removing
                 self._path_watcher.removePath(self._active_path)
            else: # If path doesn't exist, it might have been removed by OS, clear it
                 print(f"Warning: Watched path {self._active_path} no longer exists.")
        self._active_path=fdir
        if not self._path_watcher.addPath(self._active_path):
            print(f"Warning: Could not watch new path {self._active_path}")

    except Exception as e:
        QMessageBox.warning(self, "Change Directory Error", f"Could not change directory to:\n{fdir}\n\nError: {e}")


  def _update_folder(self): # Slot for QFileSystemWatcher
    self.ui.filenameList.changeDirectory(self._active_path)


  @pyqtSlot(bool) # Explicitly connect to editor's modificationChanged(bool)
  def textModified(self, modified):
    if self.openFile:
        title = f'Gnuplot Editor - {os.path.basename(self.openFile)}'
    else:
        title = 'Gnuplot Editor - Untitled' # Default for new, unsaved files
    
    if modified:
        self.setWindowTitle(title + '*')
    else:
        self.setWindowTitle(title)
    # self.fileChanged = modified # This variable is redundant if using editor.isModified()


  def aboutDialog(self):
    QMessageBox.information(self, 'About Gnuplot Editor...',
              'Gnuplot editor is written by\nArtur Glavic\n\nLicensed under GPL v.3')


  def gnuplotHelp(self):
    dia=QDialog(self)
    dia.setWindowTitle('Gnuplot Manual')
    verticalLayout=QVBoxLayout(dia)
    dia.setLayout(verticalLayout)
    
    # Determine path to help files relative to this script's location
    try:
        # __file__ should be defined if running as a script
        base_path = os.path.dirname(os.path.abspath(__file__))
    except NameError: # Fallback if __file__ is not defined (e.g. interactive, frozen)
        base_path = os.path.abspath(".") # Use CWD as a fallback

    help_index_path = os.path.join(base_path, 'htmldocs', 'index.html')

    if not os.path.exists(help_index_path):
        QMessageBox.critical(self, "Help Error", f"Help file not found:\n{help_index_path}")
        return

    if OLD_WEBWIDGET:
      webview=QtWebKitWidgets.QWebView(dia)
      webview.setUrl(QUrl.fromLocalFile(help_index_path)) # setUrl for old webkit
    else:
      webview=QtWebEngineWidgets.QWebEngineView(dia)
      webview.load(QUrl.fromLocalFile(help_index_path)) # load for new webengine
      
    verticalLayout.addWidget(webview)
    dia.resize(700, 900) # Set a reasonable default size for the help window
    dia.show()


  def addMacro(self):
    ed=self.ui.editor
    name, ok=QInputDialog.getText(self, 'Add Macro', 'Please enter a name for your new macro:')
    if ok and name: # Ensure name is not empty and user clicked OK
      name=str(name).strip() # Strip whitespace from name
      if not name: # Do not add if name is empty after stripping
          QMessageBox.warning(self, "Add Macro", "Macro name cannot be empty.")
          return

      # Get selected text or current line if no selection
      if ed.hasSelectedText():
          macro_text = str(ed.selectedText())
      else:
          macro_text = str(ed.text(ed.getCursorPosition()[0])) # Current line text
      
      add_user_macro(name, macro_text) # Assumes this updates cfg
      
      # Rebuild the user macros menu immediately
      self.ui.menuCommands.clear() 
      self._addMenuEntries(self.ui.menuCommands, cfg.items('user macros'))
    elif ok and not name: # User clicked OK but name was empty
        QMessageBox.warning(self, "Add Macro", "Macro name cannot be empty.")


  def deleteMacro(self):
    user_macros = list(cfg.items('user macros')) # Get current user macros
    if not user_macros:
        QMessageBox.information(self, "Delete Macro", "No user macros to delete.")
        return

    name_list=[item[0] for item in user_macros] # item[0] is the macro name
    delitem_name, ok=QInputDialog.getItem(self, 'Delete Macro', 'Select Macro to delete:', 
                                          name_list, editable=False) # Not editable
    if ok and delitem_name: # User selected an item and clicked OK
      del_user_macro(str(delitem_name)) # Assumes this updates cfg
      
      # Rebuild the user macros menu
      self.ui.menuCommands.clear()
      self._addMenuEntries(self.ui.menuCommands, cfg.items('user macros'))


  def changeFilelistFilters(self):
    ffilters_text=str(self.ui.filterEntry.text())
    # Split by semicolon and strip whitespace from each filter
    filters_list = [f.strip() for f in ffilters_text.split(';') if f.strip()]
    self.ui.filenameList.changeFilters(filters_list) 
    
    # Save to config
    config_value = ';'.join(filters_list)
    if sys.version_info[0] < 3: # Python 2 compatibility
        cfg.set('gui', 'data file filters', config_value.encode('utf8'))
    else:
        cfg.set('gui', 'data file filters', config_value)
    write_config() # Persist changes


  def openSearchDialog(self):
    # Create dialog if it doesn't exist or was closed, otherwise just show/raise
    if not hasattr(self, '_search_dialog_instance') or not self._search_dialog_instance.isVisible():
        self._search_dialog_instance = SearchDialog(self.ui.editor, self) # Pass editor and parent
    self._search_dialog_instance.show()
    self._search_dialog_instance.activateWindow() # Bring to front
    self._search_dialog_instance.setFocus() # Set focus to the search dialog


  def openPrintDialog(self):
    printer=Qsci.QsciPrinter() # QsciPrinter handles printing QsciScintilla content
    # Configure printer based on current editor settings (optional)
    # e.g., printer.setColourMode(self.ui.editor.colorMode())
    printer.setWrapMode(self.ui.editor.wrapMode()) # Match editor's wrap mode
    
    print_dialog=QPrintDialog(printer, self) # Pass printer and parent
    if print_dialog.exec_() == QPrintDialog.Accepted:
      doc_name = os.path.basename(self.openFile) if self.openFile else "Untitled"
      printer.setDocName(doc_name)
      try:
          printer.printRange(self.ui.editor) # Print the whole document
      except Exception as e: # QsciPrinter can sometimes raise exceptions
          QMessageBox.critical(self, "Print Error", f"Could not print document.\n\nError: {e}")


  def toggleWrapMode(self):
    if self.ui.actionWrap_Lines.isChecked():
      self.ui.editor.setWrapMode(Qsci.QsciScintilla.WrapWord)
    else:
      self.ui.editor.setWrapMode(Qsci.QsciScintilla.WrapNone)

  ####################################

  def closeEvent(self, event=None): # event can be None if called directly
    if not self._checkSave(): # If user cancels save dialog
        if event: event.ignore()
        return

    # Save window geometry and state
    settings=QSettings("AGlavic", "GnuplotEditor") # org, app name
    settings.setValue("geometry", self.saveGeometry())
    settings.setValue("windowState", self.saveState())
    
    # Save other configurations (like file filters)
    self.changeFilelistFilters() # This calls write_config() internally
    
    # Gracefully shut down the GnuplotInterface thread
    if self.gpi is not None:
        self.gpi.shutdown.set() # Signal QThread's loop to stop
        self.gpi.stopScript()   # Attempt to stop any running script in gnuplot
        self.gpi.quit()         # Ask QThread to exit event loop
        if not self.gpi.wait(2000): # Wait up to 2 seconds for thread to finish
            print("GnuplotInterface thread did not terminate gracefully, forcing.")
            # self.gpi.terminate() # Force terminate if still running (use with caution)
    
    if event: # Called from Qt close event (e.g., window X button)
        QMainWindow.closeEvent(self, event)
    else: # Called directly (e.g. File > Exit action)
        QMainWindow.close(self)


  def readSettings(self, event=None): # event is unused, for slot compatibility
    settings=QSettings("AGlavic", "GnuplotEditor")
    
    # Restore geometry and state
    try:
        geom = settings.value("geometry")
        if geom and not isinstance(geom, int): self.restoreGeometry(geom) # Check geom is not int (error case)
        state = settings.value("windowState")
        if state and not isinstance(state, int): self.restoreState(state)
    except Exception as e: # Catch potential errors during restore (e.g. corrupted data)
        print(f"Error restoring window settings: {e}")

    # Read and apply file filters from config file (not QSettings for this app's design)
    ffilters_str = cfg.get('gui', 'data file filters', fallback="*.gp;*.gpl;*.dat;*.txt")
    if sys.version_info[0] < 3 and isinstance(ffilters_str, bytes): # Python 2 decode
        ffilters_str = ffilters_str.decode('utf8', 'ignore')
    
    self.ui.filterEntry.setText(ffilters_str)
    self.ui.filenameList.changeFilters([f.strip() for f in ffilters_str.split(';') if f.strip()])


##############################################################################################
##############################################################################################

def run(args): # args is typically sys.argv
  app=QApplication(sys.argv) # Use sys.argv for QApplication
  w=MainWindow()
  w.show()
  
  # Command line argument processing to open a file
  # Allow passing a single filename argument
  if len(args) > 1: # args[0] is usually the script name itself
      file_to_open_on_startup = args[1]
      if os.path.isfile(file_to_open_on_startup) and not file_to_open_on_startup.startswith('-'):
          w.fileOpen(file_to_open_on_startup)
      # Could add more sophisticated argument parsing here if needed (e.g. using argparse)

  return app.exec_()
