import logging
import queue
import threading

import os
import sys
from pathlib import Path

LM = None

try:
    import class_ST
    HAS_SIGNAL_TRACKER=True
except ImportError:
    HAS_SIGNAL_TRACKER=False

def init_logger_manager(log_file, emit_record=False):
    global LM
    LM = LoggerManager(log_file, emit_record)
    return LM

class LoggerManager:
    """
    Central logging manager for the application.

    Logging Architecture
    --------------------
    The root logger acts as the central dispatcher for all log messages.
    Any logger created with ``propagate=True`` forwards its records to the
    root logger, which distributes them to the configured handlers.

        Root Logger
             │
      ┌──────┼──────────────┐
      │      │              │
      ▼      ▼              ▼
    File   Queue        GUI Handler
   Handler Handler           │
                             ▼
                    LoggerDock.write_GUI_Log()

    Module loggers
    --------------
    Individual modules (DatabaseManager, FileMapCliManager, MainWindow, etc.)
    obtain their own named logger. These loggers may either:

    - propagate=False
        Operate independently using only their own StreamHandler.

    - propagate=True
        Forward records to the root logger so they are written to the log
        file, placed on the logging queue, displayed in the GUI, and handled
        by any other root handlers.

            DatabaseManager
            FileMapCliManager
            MainWindow
                  │
                  └────────────► Root Logger

    Thread Safety
    -------------
    Worker threads should not update the GUI directly. Instead they emit log
    records through the SignalTracker, which forwards them to the main thread.
    The root logger then processes the records normally, allowing the GUI log
    panel to update safely.

    Responsibilities
    ----------------
    - Configure the root logger and its handlers.
    - Create and configure module loggers.
    - Forward logs to the GUI.
    - Support thread-safe logging from worker threads.
    - Optionally write logs to a file.
    """
    def __init__(self, log_file, emit_record=False):
        if log_file:
            self.log_file = Path(log_file)
        else:
            self.log_file = None
        self.log_queue = queue.Queue()
        self.root = logging.getLogger()
        self.root.setLevel(logging.DEBUG)
        self.formatter = logging.Formatter( "%(asctime)s [%(levelname)s] (%(name)s) %(message)s", "%y-%m-%d %H:%M" )

        if not self.root.handlers:
            self._setup_file_handler()
            self._setup_queue_handler(emit_record)

        self.normal_handlers= None
        self.gui_handlers = None
        self.update_thread = None
        self.st_handlers = None

    def attach_gui_handler(self, parent, emit_record=False):
        """On log emit runs write_GUI_Log function on gui_panel

        Args:
            gui_panel (QWidget): Window object with write_GUI_Log method
        """
        if self.gui_handlers:
            return
        # Create the list the first time
        if not hasattr(self, "gui_handlers") or not isinstance(self.gui_handlers,list):
            self.gui_handlers = []

        # Create a new handler for this GUI panel
        handler = ConsolePanelHandler(parent, emit_record)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            "%y-%m-%d %H:%M"
        ))

        # Add to root logger
        self.root.addHandler(handler)

        # Store it so you can manage/remove later
        self.gui_handlers.append(handler)
    
    def remove_gui_handler(self, parent):
        """
        Removes GUI logging handlers attached to a specific widget.

        The LoggerManager can attach multiple GUI handlers, for example when
        different windows or dock widgets display logging output. This method
        searches the registered GUI handlers and removes the ones associated
        with the given parent widget from the root logger.

        Removing the handler prevents future log records from being forwarded
        to that GUI instance and allows the widget to be safely destroyed
        without leaving stale references.

        Args:
            parent (QWidget):
                The GUI object that owns the logging handler. The object must
                match the parent used when calling :meth:`attach_gui_handler`.

        Returns:
            None
        """
        # The [:] copy is important because you are modifying the list while iterating over it. 
        # It avoids skipping entries if later you decide to allow multiple handlers for the same parent.
        for handler in self.gui_handlers[:]:
            if handler.parent == parent:
                self.root.removeHandler(handler)
                self.gui_handlers.remove(handler)
    
    def attach_signaltracker_handler(self, parent, signal_tracker, specific_logger:logging.Logger = None):
        """Sends emitted record through signal tracker Log_To_Main process (log_to_main signal)

        Args:
            parent (any): Not used* 
            signal_tracker (class_ST.SignalTracker): SignalTracker object connected to main log
            specific_logger (logging.Logger): If specific_logger is None, the handler is attached 
            to the root logger. Otherwise, it is attached only to specific_logger.
            Returns:
                logging.Handler | None
        """
        if not HAS_SIGNAL_TRACKER:
            return None
        if not isinstance(signal_tracker,class_ST.SignalTracker):
            return None
        handler = SignalTrackerHandler(parent, signal_tracker)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            "%y-%m-%d %H:%M"
        ))
        if not specific_logger:
            self.root.addHandler(handler)
        else:
            specific_logger.addHandler(handler)
        # Create the list the first time
        if not hasattr(self, "st_handlers") or not isinstance(self.st_handlers,list):
            self.st_handlers = []
        self.st_handlers.append((handler, specific_logger))
        return handler
    
    def remove_signaltracker_handler(
        self,
        handler,
        specific_logger: logging.Logger = None,
        ):
        """Remove a SignalTracker handler."""

        if handler is None:
            return

        if specific_logger is None:
            self.root.removeHandler(handler)
        else:
            specific_logger.removeHandler(handler)
    
    @staticmethod
    def _get_level(level: str):
        level=str(level).lower()
        level_map={
            "info":logging.INFO,
            "debug":logging.DEBUG,
            "critical":logging.CRITICAL,
            "error":logging.ERROR,
            "warning":logging.WARNING,
            "warn":logging.WARN,
            "fatal":logging.FATAL
            }
        return level_map.get(level) or level_map.get("debug")

    def get_logger_with_handler(self,name: str ,level: str="debug",propagate: bool=False,format: str=None):
        """
        Create and return a logger with its own StreamHandler.

        This logger receives its own dedicated handler (with its own level and
        formatting), and optionally forwards log records to the root logger
        depending on the `propagate` flag.

        Args:
            name (str):
                The name of the logger to create or retrieve.

            level (str, optional):
                Logging level for both the logger and its StreamHandler.
                Defaults to "debug".

            propagate (bool, optional):
                If False, the logger is isolated and does NOT forward messages
                to the root logger.  
                If True, messages are also propagated to the root logger
                (e.g., file handler, GUI handler).  
                Defaults to False.

            format (str, optional):
                Custom logging format string.  
                If None, the default format
                "%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
                is used.

        Returns:
            logging.Logger:
                The configured logger instance with its attached StreamHandler.
        """
        logger = logging.getLogger(name)
        logger.setLevel(self._get_level(level))
        # set a format which is simpler for console use
        if format is None:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
            )
        else:
            formatter = logging.Formatter(format)

        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            # define a Handler which writes INFO messages or higher to the sys.stderr
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(self._get_level(level))
            # tell the handler to use this format
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        logger.propagate = propagate
        return logger
        
    def get_new_logger_propagating_to_root(self,name,level="debug"):
        """Creates a logger and adds the logger handler to root central logger.

        Args:
            name (str): Name of the logger
        """
        return self.get_logger_with_handler(name,level,True,None)

    def start_gui_update_thread(self, killer_event):
        """Starts a thread which persistently logs True value. 
        When killer_event in a thread is set, then the signal stops.
        Used to check external device thread is connected."""
        if self.update_thread is None:
            self.update_thread = Log_Update(killer_event)
            self.update_thread.start()

    def _setup_file_handler(self):
        if self.log_file:
            fh = logging.FileHandler(self.log_file, mode="a", encoding="utf-8")
        else:
            fh = logging.StreamHandler()
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(threadName)-10s) (%(name)s) %(message)s",
            "%y-%m-%d %H:%M:%S"
        ))
        self.root.addHandler(fh)

    def _setup_queue_handler(self,emit_record=False):
        qh = QueueHandler(self.log_queue, emit_record)
        qh.setLevel(logging.DEBUG)
        qh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(threadName)-10s) %(message)s",
            "%y-%m-%d %H:%M"
        ))
        self.root.addHandler(qh)

    def get_logger(self, name):
        return logging.getLogger(name)

'''
# How to use it
LM = LoggerManager(log_file)
LM.start_gui_update_thread(killer_event)

log = LM.get_logger("main")
log.info("Application started")

'''

class QueueHandler(logging.Handler):
    """Class to send logging records to a queue
    It can be used from different threads
    The ConsoleUi class polls this queue to display records in a ScrolledText widget
    """
    # Example from Moshe Kaplan: https://gist.github.com/moshekaplan/c425f861de7bbf28ef06
    # (https://stackoverflow.com/questions/13318742/python-logging-to-tkinter-text-widget) is not thread safe!
    # See https://stackoverflow.com/questions/43909849/tkinter-python-crashes-on-new-thread-trying-to-log-on-main-thread

    def __init__(self, log_queue: queue.Queue,emit_record=False):
        super().__init__()
        self.log_queue = log_queue
        self.emit_record = emit_record

    def emit(self, record):
        if self.emit_record:
            self.log_queue.put(record)
        else:
            self.log_queue.put(self.format(record))

class ConsolePanelHandler(logging.Handler):    
    def __init__(self, parent,emit_record=True):
        logging.Handler.__init__(self)
        self.parent = parent
        self._emitting = False
        self.emit_record = emit_record
    
    def emit(self, record: logging.LogRecord):
        if self._emitting: #avoid recursion
            return
        self._emitting = True
        try:
            if self.emit_record:
                self.parent.write_GUI_Log(record)
            else:
                self.parent.write_GUI_Log(self.format(record))
        except AttributeError as eee:
            print(f"Error in ConsolePanelHandler: {eee}")
            print(f"[{record.name}] {record.message}")
        except Exception as e:
            print(f"ConsolePanelHandler error: {e}")
        finally:
            self._emitting = False

class SignalTrackerHandler(logging.Handler):
    def __init__(self, parent, signal_tracker):
        super().__init__()
        if not isinstance(signal_tracker,class_ST.SignalTracker):
            raise TypeError("Signal tracker must be a ST object")
        self.ST = signal_tracker
        self._emitting = False
        self.parent=parent

    def emit(self, record):
        if self._emitting: #avoid recursion
            return
        self._emitting = True
        # msg = self.format(record)
        # logger_name = record.name
        # level = record.levelname.lower()
        self.ST.Log_to_Main(record)
        self._emitting = False

class ToFileLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        stream_handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "[%(asctime)s][%(levelname)s] (%(threadName)-10s) %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        stream_handler.setFormatter(formatter)

        stream_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(stream_handler)
        # self.logger.propagate = False

class Log_Update(threading.Thread):
    def __init__(self,killer_event):
        threading.Thread.__init__(self, name="Log Update")
        #log.info("Log Update Started")
        self.killer_event=killer_event
        self.cycle_time=0.1
        self.ST=class_ST.SignalTracker()    
    def run(self):    
        print('Logging Thread initialized')                       
        while not self.killer_event.wait(self.cycle_time):   
            self.ST.Log_Update()
        print('Logging Thread Exit')  
    def quit(self):
        print('quit received')                                   
        self.killer_event.set()                   

def get_appPath():
    # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)
    return application_path