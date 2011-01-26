
from multiprocessing import Process
import subprocess
import os
import signal
import locale
import errno
import codecs
from logger import log

class ClosingException(Exception):
    pass


class DownloadStatus:
    DONE = 1
    ERROR = 2
    IN_PROGRESS = 3
    WAITING = 4

    def __init__(self, url, status, percent=0):
        self.status = status
        self.url = url
        self.percent= percent



class TrailerDownloader(object):
    wget_pids=[]

    def __init__(self, taskQueue, taskDict, parallelProcesses = 1):
        """taskQueue = Queue() of (url, targetDir) to download
        taskDict = dictonary with url as key and DownloadStatus as value
        parallelProcesses = number of processes downloading in parallel
        """

        self.taskQueue = taskQueue
        self.taskDict = taskDict
        self.parallelProcesses = parallelProcesses
        self.processes = []

        self._downloadFunc = TrailerDownloader.__trailer_download


    def start(self):
        for i in range(self.parallelProcesses):
            p = Process(target=TrailerDownloader.__trailer_download,
                        args=(self.taskQueue,
                              self.taskDict))
            p.start()
            self.processes.append(p)

    def stop(self):
        for p in self.processes:
            p.terminate()


    @staticmethod
    def __trailer_download(taskQueue, taskDict):
        # we need to have consistent wget output
        locale.setlocale(locale.LC_ALL, "C")
        signal.signal(signal.SIGTERM, TrailerDownloader.term_handler)
        signal.signal(signal.SIGINT, TrailerDownloader.term_handler)
        try:
            while True:
                trailerURL, targetDir = taskQueue.get()
                log.info("starting download process for %s" % trailerURL)
                command = ['wget','-cN',
                           '-U',
                           'QuickTime/7.6.2 (qtver=7.6.2;os=Windows NT 5.1Service Pack 3)',
                           trailerURL,
                           '-P',
                           targetDir,
                           '--progress=dot:mega']
                TrailerDownloader.__process_wget_output(trailerURL, command, taskDict)
        except ClosingException:
            pass


    @staticmethod
    def __process_wget_output(trailerURL, command, taskDict):
        """This function runs wget and reads its output. Each dot
        or comma counts for 65 KiB of downloaded data
        """
        log.info("executing: %s" % " ".join(command))
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        taskDict[trailerURL] = DownloadStatus(trailerURL,
                                              DownloadStatus.IN_PROGRESS)
        TrailerDownloader.wget_pids.append(p.pid)
        totalsize = 0
        while True:
            line = p.stderr.readline().decode()
            if len(line) == 0:
                break
            if line.find('Length:') != -1:
                # wget prints size of the file
                totalsize = int(line.split(' ')[1])
                break

        # now we start counting dots :-)
        downloaded = 0
        Reader = codecs.getreader("utf-8")
        stdReader = Reader(p.stderr)
        while True:
            x = stdReader.read(1)

            if len(x) == 0:
                break
            if x == '.' or x ==',':
                # comma means we are resuming so that's why we are
                # counting it too
                downloaded = downloaded + 64 * 1024
            perc = downloaded * 100 // totalsize
            if perc % 5 == 0:
                try:
                    taskDict[trailerURL] = DownloadStatus(trailerURL,
                               DownloadStatus.IN_PROGRESS,
                               perc)
                except IOError as e:
                    if e.errno is not errno.EINTR:
                        raise
                    log.debug("ignoring interrupted assignement exception")

        p.wait()
        if p.returncode is not 0:
            taskDict[trailerURL] = DownloadStatus(trailerURL,
                               DownloadStatus.ERROR)
        else:
            taskDict[trailerURL] = DownloadStatus(trailerURL,
                               DownloadStatus.DONE)
        log.info("download of %s finished with status %d" % (trailerURL, p.returncode))
        TrailerDownloader.wget_pids.remove(p.pid)

    @staticmethod
    def term_handler(signum, frame):
        """Handles closing of main process. Stops running wget downloads"""
        for p in TrailerDownloader.wget_pids:
            log.info('stopping wget process %d' % p)
            os.kill(p, signal.SIGTERM)
        raise ClosingException("Finishing up")
