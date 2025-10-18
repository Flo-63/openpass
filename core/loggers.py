"""
===============================================================================
Project   : openpass
Module    : core/loggers.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This module provides logging utilities for the openpass application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

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
    Provides functionality to create and manage standard logging formatters.

    The LogFormatter class is designed to standardize logging output with predefined
    formats for message and date-time logging. It simplifies the process of creating
    consistent log outputs across different modules.

    Attributes:
        DEFAULT_FORMAT: str
            Defines the default format for logging messages.
        DEFAULT_DATE_FORMAT: str
            Defines the default format for displaying dates and times in log messages.
    """
    DEFAULT_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    @classmethod
    def get_text_formatter(cls) -> logging.Formatter:
        """Returns a standard text formatter for logging"""
        return logging.Formatter(cls.DEFAULT_FORMAT, cls.DEFAULT_DATE_FORMAT)


class JSONFormatter(logging.Formatter):
    """
    Formats log records into JSON format.

    The JSONFormatter class formats logging records into JSON format, including
    details such as the timestamp, logging level, logger name, module, function name,
    line number, and the log message. It optionally includes exception information
    if present in the log record.
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
    Configures logging for the application.

    The LoggerConfig class sets up logging paths and determines log levels
    based on the application's configuration. It ensures that necessary
    directories for storing logs are created and that the log levels for
    different operations are properly defined.

    Attributes:
        app: The application object providing configuration details.
        project_root: The path to the root directory of the project.
        log_levels: A dictionary mapping log categories to their respective
                    logging levels.
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
    Configures logging for the given application by setting up multiple loggers with
    specified levels, paths, and behaviors. The function utilizes dynamic logger
    configuration based on application settings and predefined logging rules.

    Parameters:
    app: The application instance for which the logging is being configured.
         Expected to have configuration attributes like SERVER_LOG_PATH and LOG_PATH.

    Returns:
    None
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
    Configures and returns a logger instance with specified attributes.

    The function creates a logger with the provided name and configures it to write
    log messages to a file specified by `log_path` and `base_name`. Optionally,
    console output can be enabled with a specific logging level for the console. The
    logger uses a rotating file handler to manage log file size and backups.

    Parameters:
    name: str
        Name of the logger to configure. This is typically the module or component
        name.
    base_name: str
        Base file name to use when creating log files for this logger.
    level: int
        Logging level for the main logger and file handler (e.g., logging.DEBUG)
    log_path: Union[str, Path]
        Path where the log files will be stored.
    console_output: bool, optional
        Whether to enable logging to the console. Default is False.
    console_level: Optional[int], optional
        Logging level for console output (e.g., logging.ERROR). Required only if
        console_output is True.
    delay: bool, optional
        Whether to delay file creation for the log handler until the first log
        is written. Default is False.

    Returns:
    logging.Logger
        Configured logger instance.
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