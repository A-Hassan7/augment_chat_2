import logging

import colorlog

# create logger class
# create and add handlers (stdout, filehandler)
# create and add formatter
# color logs would be nice


class Logger:

    _instances = {}

    def __new__(cls, *args, **kwargs):
        """
        Returned existing logger class if already initialised

        Returns:
            _type_: _description_
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Logger, cls).__new__(cls)
        return cls._instances[cls]

    def __init__(self, file: str = "./logs.txt", level: str = "DEBUG"):
        self.file = file
        self.level = level

    def get_logger(self, name: str) -> logging.Logger:
        """
        Returns a logger configured for the specific name provided

        Args:
            name (str): name of logger to return
        """

        if name in self._instances:
            return self._instances[name]

        # create logger
        logger = logging.getLogger(name)

        # create formatter
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S,%f",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )

        # create and add handlers
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

        file_handler = logging.FileHandler(filename=self.file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.setLevel(self.level)

        self._instances[name] = logger

        return logger
