# loggers.py
# Standard Library
import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import (
    Dict,
    Optional,
    Union
)


class LogFormatter:
    """
    Provides utility for creating standardized log formatters.

    This class includes methods for creating and configuring log formatters
    with a default format and date format suitable for consistent log
    formatting in applications.

    :cvar DEFAULT_FORMAT: Default format string for logs.
    :type DEFAULT_FORMAT: str
    :cvar DEFAULT_DATE_FORMAT: Default date format for log timestamps.
    :type DEFAULT_DATE_FORMAT: str
    """
    DEFAULT_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    @classmethod
    def get_text_formatter(cls) -> logging.Formatter:
        """Returns a standard text formatter for logging"""
        return logging.Formatter(cls.DEFAULT_FORMAT, cls.DEFAULT_DATE_FORMAT)


class JSONFormatter(logging.Formatter):
    """
    Formatter class for logging that outputs log records in JSON format.

    This class inherits from the logging.Formatter base class and is used
    to format log records as JSON objects. Each log record is serialized
    into a JSON string containing details such as the timestamp, log level,
    logger name, log message, module, function, and line number, as well as
    exception details if applicable.

    :ivar default_time_format: The default datetime format used for log timestamps.
    :type default_time_format: str
    :ivar default_msec_format: The default format for milliseconds in time.
    :type default_msec_format: str
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formats log record as JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class LoggerConfig:
    """
    Handles configuration and setup of logging for the application.

    The LoggerConfig class is responsible for configuring log directories and
    log levels for the application. It ensures that all required log directories
    are created and uses the application's configuration to determine appropriate
    settings for various logging aspects.

    :ivar app: Reference to the application object for accessing its configuration.
    :type app: Any
    :ivar project_root: Path object pointing to the root directory of the project.
    :type project_root: Path
    :ivar log_levels: Dictionary mapping log categories to their respective log levels.
    :type log_levels: Dict[str, int]
    """

    def __init__(self, app):
        self.app = app
        self.project_root = Path(__file__).parent.parent
        self._configure_paths()
        self.log_levels = self._get_log_levels()

    def _configure_paths(self) -> None:
        """Configures and creates log directories"""
        if not self.app.config.get('LOG_PATH'):
            self.app.config['LOG_PATH'] = str(self.project_root / 'logs')

        # Create directories if they don't exist
        for path in [self.app.config['LOG_PATH'],
                    self.app.config.get('SERVER_LOG_PATH', self.app.config['LOG_PATH'])]:
            Path(path).mkdir(parents=True, exist_ok=True)

    def _get_log_levels(self) -> Dict[str, int]:
        """Determines configured log levels"""
        return {
            'main': getattr(logging, self.app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO),
            'console': getattr(logging, self.app.config.get('CONSOLE_LOG_LEVEL', 'INFO').upper(), logging.INFO),
            'import': getattr(logging, self.app.config.get('IMPORT_LOG_LEVEL', 'INFO').upper(), logging.INFO),
            'task': getattr(logging, self.app.config.get('TASK_LOG_LEVEL', 'INFO').upper(), logging.INFO),
            'auth': getattr(logging, self.app.config.get('AUTH_LOG_LEVEL', 'INFO').upper(), logging.INFO),
            'csp': getattr(logging, self.app.config.get('CSP_LOG_LEVEL', 'INFO').upper(), logging.INFO)
        }


def configure_logging(app) -> None:
    """
    Configures logging for the given application. This setup initializes multiple 
    loggers with specific configurations, such as log level, log destinations 
    (server or console), and behavior like delay handling. The function uses 
    the LoggerConfig class to determine log levels for different components of 
    the application, and it establishes loggers with these configurations using 
    the Setup_logger utility.

    :param app: The application instance for which logging is being configured. 
               This is expected to have configuration attributes like 
               `SERVER_LOG_PATH` and `LOG_PATH` to define log output paths.
    :type app: Any
    :return: None
    """
    config = LoggerConfig(app)

    # Logger definitions with both formats
    loggers = {
        'main_logger': {
            'base_name': 'main',
            'level': config.log_levels['main'],
            'console': True
        },
        'import_logger': {
            'base_name': 'import',
            'level': config.log_levels['import']
        },
        'auth_logger': {
            'base_name': 'auth',
            'level': config.log_levels['auth']
        },
        'csp_logger': {
            'base_name': 'csp',
            'level': config.log_levels['csp'],
            'server_log': True,
            'delay': True
        }
    }

    for logger_name, logger_config in loggers.items():
        Setup_logger(
            name=logger_name,
            base_name=logger_config['base_name'],
            level=logger_config['level'],
            log_path=app.config['SERVER_LOG_PATH'] if logger_config.get('server_log')
            else app.config['LOG_PATH'],
            console_output=logger_config.get('console', False),
            console_level=config.log_levels['console'],
            delay=logger_config.get('delay', False)
        )


def Setup_logger(
        name: str,
        base_name: str,
        level: int,
        log_path: Union[str, Path],
        console_output: bool = False,
        console_level: Optional[int] = None,
        delay: bool = False
) -> logging.Logger:
    """
    Sets up a logger with specified configuration, including rotating file handler
    and optional console output.

    The logger is created with the provided name and level. It uses a rotating
    file handler to log to a specified path, with optional inclusion of
    console output. The function ensures that handlers are not duplicated
    when the logger is retrieved multiple times.

    :param name: Name of the logger to be configured.
    :param base_name: Base name for the log file.
    :param level: Logging level for the logger.
    :param log_path: Path where the log file will be stored.
    :param console_output: Whether to output logs to console (default: False).
    :param console_level: Logging level for console output (default: None).
    :param delay: Whether to delay file creation until first log (default: False).
    :return: Configured logger instance.
    :rtype: logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler_config = {
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 6,
            'encoding': 'utf-8',
            'delay': delay
        }

        # Text handler configuration
        text_handler = RotatingFileHandler(
            filename=str(Path(log_path) / f"{base_name}.log"),
            **handler_config
        )
        text_handler.setFormatter(LogFormatter.get_text_formatter())
        text_handler.setLevel(level)
        logger.addHandler(text_handler)

        # Console output configuration
        if console_output and console_level:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(console_level)
            console_handler.setFormatter(LogFormatter.get_text_formatter())
            logger.addHandler(console_handler)

            # Add error handler for console if console level is ERROR
            if console_level == logging.ERROR:
                error_handler = logging.StreamHandler(sys.stderr)
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(LogFormatter.get_text_formatter())
                logger.addHandler(error_handler)

        logger.debug(f"{name} Logger has been configured")
        logger.propagate = True

    return logger