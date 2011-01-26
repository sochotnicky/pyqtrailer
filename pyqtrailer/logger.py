import logging
from logging.handlers import RotatingFileHandler
import os
log = logging

def setup_log():
    logger = log.getLogger("")
    logger.setLevel(logging.DEBUG)
    # 1 MB file max
    fh = RotatingFileHandler("%s/.pyqtrailer.log" % os.path.expanduser('~'),
                             'a', 1000000, 1)
    fh.setLevel(logging.DEBUG)

    # console logger
    ch = logging.StreamHandler()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    # add the handlers to logger
    logger.addHandler(ch)
    logger.addHandler(fh)
