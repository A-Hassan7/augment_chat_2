import logging

import colorlog
# create logger class
# create and add handlers (stdout, filehandler)
# create and add formatter
# color logs would be nice

class Logger:

    FILENAME = './logs.txt'

    def get_logger(self, name: str) -> logging.Logger:
        """
        Returns a logger configured for the specific name provided

        Args:
            name (str): name of logger to return
        """

        # create logger
        logger = logging.getLogger(name)

        # create formatter
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S,%f',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        )

        # create and add handlers
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

        file_handler = logging.FileHandler(filename=self.FILENAME)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.setLevel('DEBUG')

        return logger