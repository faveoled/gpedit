#-*- coding: utf-8 -*-
'''
QThread that interacts with gnuplot directly to execute the scripts.
This is needed in oder not to block the editor when the script is running.
'''

import os
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired
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
  processCrashed = pyqtSignal() 

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
    self.gp = None # Initialize self.gp here
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
      except IOError: # This can happen if gnuplot process dies or _write fails
        print("IOError in GnuplotInterface run loop, re-initializing Gnuplot.")
        # initGnuplot might raise RuntimeError if it can't start gnuplot
        try:
            self.initGnuplot()
        except RuntimeError as e_init:
            print(f"Fatal error during Gnuplot re-initialization: {e_init}. Thread might stop if not recoverable.")
            # If initGnuplot fails critically (e.g., gnuplot not found), emit crash and maybe stop thread.
            self.processCrashed.emit() # Ensure UI knows
            self.shutdown.set() # Signal thread to stop if Gnuplot cannot be re-initialized
            break # Exit run loop
      except RuntimeError as e: # Catch RuntimeError from executeLine/pickPosition/initGnuplot
        if 'Gnuplot terminated' in str(e) or 'Gnuplot could not be started' in str(e) or 'Gnuplot EOF' in str(e) or 'Gnuplot stdout read error' in str(e) or 'Failed Gnuplot initialization' in str(e):
            print(f"RuntimeError caught in run loop: {e}. Gnuplot (re-)initialization will be attempted or has occurred.")
            # If error is from initGnuplot itself (e.g. could not start), it might have emitted processCrashed.
            # If from executeLine/pickPosition, they emit processCrashed and then raise RuntimeError, leading here.
            # The goal here is to ensure initGnuplot is called if a recoverable runtime error occurs.
            if "Gnuplot could not be started" not in str(e) and "Failed Gnuplot initialization" not in str(e) : # If it's not a startup error, try re-init.
                try:
                    self.initGnuplot()
                except RuntimeError as e_reinit:
                    print(f"Fatal error during Gnuplot re-initialization from run loop: {e_reinit}")
                    self.processCrashed.emit()
                    self.shutdown.set() # Stop thread if re-init fails
                    break
            else: # Gnuplot could not be started or init failed, already handled by initGnuplot, stop thread.
                self.shutdown.set() # Ensure thread stops
                break

        else: # Other unexpected RuntimeErrors
            traceback.print_exc() 
            try:
                self.initGnuplot() 
            except RuntimeError as e_reinit_other:
                print(f"Fatal error during Gnuplot re-initialization for other RuntimeError: {e_reinit_other}")
                self.processCrashed.emit()
                self.shutdown.set()
                break
      except Exception: # Catch all other exceptions
        traceback.print_exc()
        print("Unexpected exception in GnuplotInterface run loop, attempting re-initialization.")
        try:
            self.initGnuplot()
        except RuntimeError as e_reinit_exc:
            print(f"Fatal error during Gnuplot re-initialization for general exception: {e_reinit_exc}")
            self.processCrashed.emit()
            self.shutdown.set()
            break
    print("GnuplotInterface run loop ended.")


  def _run(self):
    # This inner loop runs as long as the thread is not shut down.
    # It waits for script commands or shutdown signals.
    while not self.shutdown.isSet():
      if self.script: # If there are commands in the queue
        self.scriptIdle.clear() # Mark as not idle
        self.executeLine() # Execute the next command
      else: # No commands in the queue
        if not self.scriptIdle.is_set():
            self.scriptIdle.set() # Mark as idle
        # Wait for a short period or until shutdown is signaled.
        # This allows the thread to be responsive to new commands or shutdown requests.
        self.shutdown.wait(0.05) # 50ms wait, adjust as needed for responsiveness


  def initGnuplot(self):
    # --- Start of new cleanup block for existing self.gp ---
    if hasattr(self, 'gp') and self.gp is not None:
        print("Cleaning up existing Gnuplot process before re-initialization...")
        if self.gp.poll() is None:  # Process is running
            try:
                if hasattr(self.gp, 'stdin') and self.gp.stdin and not self.gp.stdin.closed:
                    self.gp.stdin.close()
            except (IOError, AttributeError) as e:
                print(f"Error closing stdin of old Gnuplot process: {e}")

            self.gp.terminate()
            try:
                self.gp.wait(timeout=0.5)
            except TimeoutExpired:
                print("Old Gnuplot process did not terminate in time, killing...")
                self.gp.kill()
                try:
                    self.gp.wait(timeout=0.5)
                except TimeoutExpired:
                    print("Old Gnuplot process did not die after kill. May be orphaned.")
                except Exception as e: # pylint: disable=broad-except
                    print(f"Exception waiting for old Gnuplot to die after kill: {e}")
            except Exception as e: # pylint: disable=broad-except
                print(f"Exception waiting for old Gnuplot to terminate: {e}")
        
        # Try to close stdout/stderr streams if they exist and are open
        for stream_name in ['stdout', 'stderr']:
            if hasattr(self.gp, stream_name):
                stream = getattr(self.gp, stream_name)
                if stream and hasattr(stream, 'closed') and not stream.closed: # Check if stream obj exists and has 'closed' attr
                    try:
                        stream.close()
                    except (IOError, AttributeError) as e: # AttributeError for None or missing 'closed'
                        print(f"Error closing {stream_name} of old Gnuplot process: {e}")
        self.gp = None
    # --- End of new cleanup block ---

    self.term_options=dict(self.parent._default_term_options)
    extra_opts={"bufsize": 0}
    gp_executable='gnuplot' # Default, rely on PATH

    # Platform-specific executable path finding
    if win32process is not None: # Windows
      extra_opts['creationflags']=win32process.CREATE_NO_WINDOW
      module_dir = os.path.dirname(__file__) 
      gp_bundled_path = os.path.join(module_dir, '..', 'gnuplot', 'bin', 'gnuplot.exe')
      if os.path.exists(gp_bundled_path): 
          gp_executable = gp_bundled_path
          print(f"Using specific Gnuplot for Windows: {gp_executable}")
      else:
          print(f"Specific Gnuplot for Windows not found at {gp_bundled_path}, relying on PATH for 'gnuplot'.")
    
    try: 
      print(f"Attempting to start Gnuplot with: '{gp_executable}'")
      self.gp=Popen(gp_executable, stdin=PIPE, stdout=PIPE, stderr=STDOUT, **extra_opts)
    except OSError as e_main: 
      print(f"Failed to start Gnuplot with '{gp_executable}': {e_main}. Trying common alternatives...")
      alternatives = ['/usr/bin/gnuplot', '/usr/local/bin/gnuplot', '/opt/local/bin/gnuplot', '/opt/homebrew/bin/gnuplot']
      if os.name == 'nt': 
          program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
          program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
          alternatives.extend([
              os.path.join(program_files, "gnuplot", "bin", "gnuplot.exe"),
              os.path.join(program_files_x86, "gnuplot", "bin", "gnuplot.exe"),
          ])
      
      found_alternative = False
      for alt_path in alternatives:
          if os.path.exists(alt_path): 
            try:
                print(f"Attempting alternative Gnuplot path: '{alt_path}'")
                self.gp = Popen(alt_path, stdin=PIPE, stdout=PIPE, stderr=STDOUT, **extra_opts)
                print(f"Successfully started Gnuplot with alternative: '{alt_path}'.")
                found_alternative = True
                break 
            except OSError:
                print(f"Alternative '{alt_path}' also failed.")
          else:
              print(f"Alternative path '{alt_path}' does not exist.")

      if not found_alternative:
          print("All attempts to start Gnuplot failed.")
          self.gp = None 
          self.processCrashed.emit() 
          raise RuntimeError("Gnuplot could not be started. Please ensure it is installed and in your system's PATH or configured correctly.")

    try:
        if self.gp is None: 
             raise IOError("Gnuplot process (self.gp) is None after Popen attempts.")

        self._write('print GPVAL_TERMINALS\n')
        self._write('print "====Command End===="\n')
        
        outstr_response=''
        # --- Start of modification for GPVAL_TERMINALS read loop ---
        max_bytes_initial_read = 2048 # Increased limit
        bytes_received_count = 0     # Renamed counter
        while not outstr_response.endswith('====Command End===='):
            if self.gp.poll() is not None: 
                raise IOError("Gnuplot terminated during init while reading GPVAL_TERMINALS.")
            
            if bytes_received_count > max_bytes_initial_read: # Condition updated
                if self.gp.poll() is None: self.gp.kill()
                raise TimeoutError(f"Timeout reading GPVAL_TERMINALS from Gnuplot (read {bytes_received_count} bytes). Received so far: '{outstr_response}'")

            next_char_bytes = self.gp.stdout.read(1) 
            if not next_char_bytes:  
                if self.gp.poll() is not None or (hasattr(self.gp.stdout, 'readable') and not self.gp.stdout.readable()): 
                    raise IOError("Gnuplot EOF (process died) during init while reading GPVAL_TERMINALS.")
                else: 
                    print("Warning: Gnuplot stdout.read(1) returned EOF but process seems alive. Retrying read.")
                    QThread.msleep(10) 
            else:
                outstr_response += str(next_char_bytes, 'ascii', 'replace')
            bytes_received_count += 1 # Counter incremented
        # --- End of modification for GPVAL_TERMINALS read loop ---

        outstr_response = outstr_response.split('====Command End====')[0].strip()
        available_terms = outstr_response.split()
        
        chosen_term_type = self.TERMINALS['order'][0] 
        for term_type in self.TERMINALS['order']:
          if term_type in available_terms:
            chosen_term_type = term_type
            break
        self.parent.preview_term = self.TERMINALS[chosen_term_type]
        print(f"Selected preview terminal type: {chosen_term_type} -> {self.parent.preview_term}")
        
        init_term_opts = dict(self.parent._default_term_options) 
        init_term_opts['n'] = 1 
        self.write(self.parent.preview_term % init_term_opts)

    except (IOError, TimeoutError, RuntimeError) as e: 
        print(f"Error communicating with Gnuplot during initialization: {e}")
        if self.gp and self.gp.poll() is None: 
            self.gp.kill()
        self.gp = None 
        self.processCrashed.emit() 
        raise RuntimeError(f"Failed Gnuplot initialization: {e}")


  @pyqtSlot()
  def clear(self):
    if not self.scriptIdle.is_set():
        if not self.scriptIdle.wait(timeout=1.0): 
            print("GnuplotInterface.clear(): Timed out waiting for script to become idle. Proceeding with clear.")
    self.write('unset output')
    self.write('reset')

  @pyqtSlot(str, int)
  @pyqtSlot(str)
  def write(self, line, lno=-1):
    self.script.append((line, lno))

  def _write(self, line):
    if self.gp is None or self.gp.stdin is None: 
        print("Error: Gnuplot process or stdin is not available (gp or gp.stdin is None).")
        self.processCrashed.emit()
        raise IOError("Gnuplot process or stdin is None.")
    
    if self.gp.stdin.closed: 
        print("Error: Gnuplot stdin is closed.")
        if self.gp.poll() is not None: 
            print("Gnuplot process terminated, cannot write to stdin.")
        self.processCrashed.emit() 
        raise IOError("Gnuplot stdin is closed.")

    try:
        self.gp.stdin.write(line.encode(self.encoding))
        self.gp.stdin.flush() 
    except (IOError, BrokenPipeError, AttributeError) as e: 
        print(f"Error writing to Gnuplot stdin: {e}")
        if self.gp.poll() is not None:
            print("Gnuplot process appears to have terminated.")
        self.processCrashed.emit()
        raise IOError(f"Gnuplot stdin write error: {e}")


  @pyqtSlot()
  def stopScript(self):
    print("stopScript called.")
    self.shutdownScript.clear() 
    self._doShutdown = True 

    if not hasattr(self, 'gp') or self.gp is None or self.gp.poll() is not None:
        print("stopScript: Gnuplot process not running or already terminated.")
        self.script = [] 
        if not self.scriptIdle.is_set(): self.scriptIdle.set()
        self._doShutdown = False 
        self.shutdownScript.set() 
        return

    print("stopScript: Attempting to stop running Gnuplot script.")
    QThread.msleep(50) 

    if self.gp.poll() is None: 
        print("stopScript: Gnuplot still running, proceeding to terminate.")
        self.gp.terminate()
        try:
            self.gp.wait(timeout=0.5) 
        except TimeoutExpired:
            print("stopScript: Gnuplot did not terminate after 0.5s, killing...")
            self.gp.kill()
            try:
                self.gp.wait(timeout=0.5)
            except TimeoutExpired:
                print("stopScript: Gnuplot did not die after kill.")
            except Exception: pass 
        except Exception: pass 
    
    self.script = [] 
    if not self.scriptIdle.is_set(): self.scriptIdle.set()
    self._doShutdown = False 
    self.shutdownScript.set() 
    print("stopScript finished.")


  def executeLine(self):
    if not self.script: 
        if not self.scriptIdle.is_set(): self.scriptIdle.set()
        return

    next_item = self.script.pop(0)
    if not self.script: 
        if not self.scriptIdle.is_set(): self.scriptIdle.set()
    
    if isinstance(next_item, str):
      try:
          method_to_call = getattr(self, next_item)
          method_to_call()
      except AttributeError:
          print(f"Error: Internal command '{next_item}' not found in GnuplotInterface.")
          self.lineExecuted.emit(False, f"Internal error: Unknown command {next_item}", -1)
      return 

    line, lno = next_item

    if line is None: 
      if lno > 0: 
        self.imagesFinished.emit(lno)
      else: 
        self.scriptFinished.emit()
      return

    try:
        self._write(line+'\n')
        if lno>=0: 
          self.lineSend.emit(('[% 3i] '%lno)+line.replace('\n', '\n      ')+'\n', lno)
        else: 
          self.lineSend.emit('gnuplot> '+line+'\n', lno)
        self._write('print "====Command End===="\n')
    except IOError as e: 
        print(f"executeLine: IOError during _write: {e}. Aborting line execution.")
        if not self.script and not self.scriptIdle.is_set():
            self.scriptIdle.set()
        raise 

    outstr_bytes = b''
    try:
        while not outstr_bytes.endswith(b'====Command End===='):
            if self.gp is None or self.gp.poll() is not None: 
                if self._doShutdown: 
                    self._doShutdown = False 
                    decoded_output = outstr_bytes.strip().decode(self.encoding, 'replace')
                    self.lineExecuted.emit(True, decoded_output + '\n\nGnuplot script execution stopped by user.', -1)
                    return 
                
                print("executeLine: Gnuplot terminated unexpectedly during command output reading.")
                decoded_output = outstr_bytes.strip().decode(self.encoding, 'replace')
                self.lineExecuted.emit(False, decoded_output + '\n\nGnuplot process terminated unexpectedly.', lno)
                self.script = [] 
                if not self.scriptIdle.is_set(): self.scriptIdle.set()
                self.processCrashed.emit() 
                raise RuntimeError('Gnuplot terminated unexpectedly while reading output in executeLine')

            if self.gp.stdout is None: raise IOError("Gnuplot stdout is None during read.")
            next_byte = self.gp.stdout.read(1) 
            if not next_byte: 
                print("executeLine: EOF reading Gnuplot stdout, process likely died.")
                if self._doShutdown: self._doShutdown = False; return 
                
                if self.gp.poll() is None: 
                    QThread.msleep(20) 
                    if self.gp.poll() is None: 
                         print("executeLine: EOF on stdout but process poll is None. Gnuplot might be stuck or pipe error.")
                
                decoded_output = outstr_bytes.strip().decode(self.encoding, 'replace')
                self.lineExecuted.emit(False, decoded_output + '\n\nGnuplot process EOF reached unexpectedly.', lno)
                self.script = []
                if not self.scriptIdle.is_set(): self.scriptIdle.set()
                self.processCrashed.emit()
                raise RuntimeError('Gnuplot EOF while reading output in executeLine')
            outstr_bytes += next_byte
            
    except IOError as e: 
        print(f"executeLine: IOError reading Gnuplot stdout: {e}")
        if self._doShutdown: self._doShutdown=False; return 
        self.script = []; self.processCrashed.emit()
        if not self.scriptIdle.is_set(): self.scriptIdle.set()
        raise RuntimeError(f'Gnuplot stdout read error: {e}') 
    except RuntimeError: 
        raise

    outstr_decoded = outstr_bytes.decode(self.encoding, 'replace').split('====Command End====')[0].strip()
    err_detected = 'gnuplot>' in outstr_decoded or \
                   '"<stdin>"' in outstr_decoded or \
                   'line 0:' in outstr_decoded or \
                   'error:' in outstr_decoded.lower() or \
                   'undefined' in outstr_decoded.lower()

    if lno >= 0 and err_detected:
        if not (f"line {lno}:" in outstr_decoded or f"\"{lno}\"" in outstr_decoded):
             outstr_decoded = f"[Script line {lno}] {outstr_decoded}"
    
    self.lineExecuted.emit(not err_detected, outstr_decoded.strip(), lno)


  def _pickPosition(self): 
    if self.gp is None or self.gp.poll() is not None:
        print("_pickPosition: Gnuplot not running.")
        self.lineExecuted.emit(False, "Gnuplot not running for pickPosition.", -1)
        return

    try:
        self._write('pause mouse\n')
        self._write('print "x=",MOUSE_X\n')
        self._write('print "y=",MOUSE_Y\n')
        self._write('print "====Command End===="\n')
    except IOError as e:
        print(f"_pickPosition: IOError during _write: {e}. Aborting pick.")
        if not self.script and not self.scriptIdle.is_set():
            self.scriptIdle.set()
        raise 

    outstr_bytes = b''
    try:
        while not outstr_bytes.endswith(b'====Command End===='):
            if self.gp.poll() is not None: 
                if self._doShutdown: 
                    self._doShutdown = False
                    self.lineExecuted.emit(True, outstr_bytes.strip().decode(self.encoding, 'replace') + '\n\nPick position stopped by user.', -1)
                    return
                
                print("_pickPosition: Gnuplot terminated unexpectedly.")
                decoded_output = outstr_bytes.strip().decode(self.encoding, 'replace')
                self.lineExecuted.emit(False, decoded_output + '\n\nGnuplot process terminated unexpectedly during pickPosition.', -1)
                self.script = []
                if not self.scriptIdle.is_set(): self.scriptIdle.set()
                self.processCrashed.emit()
                raise RuntimeError('Gnuplot terminated unexpectedly during _pickPosition read')

            if self.gp.stdout is None: raise IOError("Gnuplot stdout is None during pickPosition read.")
            next_byte = self.gp.stdout.read(1)
            if not next_byte: # EOF
                print("_pickPosition: EOF reading Gnuplot stdout.")
                if self._doShutdown: self._doShutdown = False; return
                self.script = []; self.processCrashed.emit()
                if not self.scriptIdle.is_set(): self.scriptIdle.set()
                raise RuntimeError('Gnuplot EOF during _pickPosition read')
            outstr_bytes += next_byte
    except IOError as e:
        print(f"_pickPosition: IOError reading Gnuplot stdout: {e}")
        if self._doShutdown: self._doShutdown=False; return
        self.script=[]; self.processCrashed.emit()
        if not self.scriptIdle.is_set(): self.scriptIdle.set()
        raise RuntimeError(f'Gnuplot stdout read error during pickPosition: {e}')
    except RuntimeError:
        raise 

    outstr_decoded = outstr_bytes.decode(self.encoding, 'replace').split('====Command End====')[0].strip()
    
    x_val, y_val = 0.0, 0.0
    err_in_output = 'gnuplot>' in outstr_decoded or \
                    "undefined variable: MOUSE_X" in outstr_decoded or \
                    ("MOUSE_Y" in outstr_decoded and "undefined" in outstr_decoded)
    
    if not err_in_output:
        try:
          lines_from_gp = outstr_decoded.splitlines()
          found_x, found_y = False, False
          for l_item in lines_from_gp:
              if l_item.startswith('x='):
                  x_val = float(l_item.split('x=')[1].strip())
                  found_x = True
              elif l_item.startswith('y='):
                  y_val = float(l_item.split('y=')[1].strip())
                  found_y = True
          if not (found_x and found_y): 
              if not ("pause mouse" in outstr_decoded and not lines_from_gp): 
                if not ("pause mouse" in outstr_decoded and not any(s.startswith("x=") or s.startswith("y=") for s in lines_from_gp)):
                    print(f"Could not parse MOUSE_X/Y. Output: {outstr_decoded}")
                    err_in_output = True 
        except (ValueError, IndexError) as e:
          print(f"Error parsing MOUSE_X/Y from gnuplot: {e}\nOutput was: {outstr_decoded}")
          err_in_output = True

    self.lineExecuted.emit(not err_in_output, outstr_decoded, -1) 
    if not err_in_output:
        self.mousePicked.emit(x_val, y_val)
