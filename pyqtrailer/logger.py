import logging
import os
log = logging
log.basicConfig(level=log.DEBUG, format='%(asctime)s %(levelname)s %(message)s',
                            filename="/tmp/pyqtrailer.%d.log" % os.getpid(), filemode='w')
