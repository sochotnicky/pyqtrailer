
import sys
import os
import re
import pickle
import multiprocessing
import ConfigParser as configparser
import random

from PyQt4.QtCore import *
from PyQt4.QtGui import *


from qtcustom import *
import pytrailer as amt
from downloader import TrailerDownloader, DownloadStatus

categories = [('Just added', '/trailers/home/feeds/just_added.json'),
              ('Exclusive', '/trailers/home/feeds/exclusive.json'),
              ('Only HD', '/trailers/home/feeds/just_hd.json'),
              ('Most popular', '/trailers/home/feeds/most_pop.json'),
              ('Search', '/trailers/home/scripts/quickfind.php?callback=searchCallback&q=')]


class PyTrailerWidget(QMainWindow):
    configPath = '%s/.pyqtrailer' % os.path.expanduser('~')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        READ_AHEAD_PROC=4
        self.config = configparser.SafeConfigParser({'downloadDir':'/tmp',
                                       'filters':pickle.dumps([])})
        self.config.read(self.configPath)
        self.movieDict = {}
        self.readAheadTaskQueue = multiprocessing.Queue()
        self.readAheadDoneQueue = multiprocessing.Queue()
        self.trailerDownloadQueue = multiprocessing.Queue()
        self.trailerDownloadDict = multiprocessing.Manager().dict()

        self.readAheadProcess = []
        for i in range(READ_AHEAD_PROC):
            p = multiprocessing.Process(target=movieReadAhead,
                        args=(self.readAheadTaskQueue,
                              self.readAheadDoneQueue))
            p.start()
            self.readAheadProcess.append(p)

        self.downloader = TrailerDownloader(self.trailerDownloadQueue,
                               self.trailerDownloadDict,
                               2)
        self.downloader.start()
        self.init_widget()
        self.init_menus()

    def init_widget(self):

        self.refreshTimer = QTimer(self)
        self.refreshTimer.timeout.connect(self.refreshMovies)
        self.refreshTimer.start(1000)
        self.setWindowTitle(self.tr("PyTrailer - Apple Trailer Downloader"))

        centralWidget = QWidget()
        hbox = QHBoxLayout()
        group = QButtonGroup(hbox)
        group.setExclusive(True)
        for cat, url in categories:
            but = QPushButton(cat, self)
            but.setCheckable(True)
            group.addButton(but)
            hbox.addWidget(but)

        group.buttonClicked.connect(self.groupChange)

        self.scrollArea = QScrollArea(centralWidget)
        scrollArea = self.scrollArea
        self.scrolledWidget = QWidget(scrollArea)
        scrolledWidget = self.scrolledWidget
        self.hackTmp = scrolledWidget


        statusView = QTreeWidget(centralWidget)
        statusView.setMaximumHeight(200)
        statusView.setHeaderLabels(["Trailer","Download status"])
        statusView.setVisible(False)
        statusView.setRootIsDecorated(False)
        statusView.setColumnWidth(0, self.width()-200)
        self.statusView = statusView
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(scrollArea)
        vbox.addWidget(statusView)
        mlistLayout = QVBoxLayout()
        scrolledWidget.setLayout(mlistLayout)
        scrollArea.setWidget(scrolledWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumSize(QSize(400,350))

        self.mainArea = mlistLayout
        self.loadGroup("Just added")
        centralWidget.setLayout(vbox)
        self.setCentralWidget(centralWidget)

    def init_menus(self):
        fileMenu = self.menuBar().addMenu(self.tr("&File"));

        fileMenu.addAction(self.tr("Settings"), self.settings,
                           QKeySequence(self.tr("Ctrl+S",
                                                "File|Settings")))
        fileMenu.addAction(self.tr("Quit"), self.close,
                           QKeySequence(self.tr("Ctrl+Q",
                                                "File|Quit")))

        movieMenu = self.menuBar().addMenu(self.tr("&Movies"))
        i=1
        for cat, url in categories:
            movieMenu.addAction(self.tr(cat), self.slotCreate(cat),
                                QKeySequence(self.tr("F%d" % i,
                                "Movies|%s" % cat)))
            i = i + 1
        aboutMenu = self.menuBar().addMenu(self.tr("&Help"))

        aboutMenu.addAction(self.tr("&About"),
                            self.about,
                            QKeySequence(self.tr("Ctrl+A",
                                                 "Help|About PyQTrailer")))

    def settings(self):
        d = PyTrailerSettings(self.config)
        if d.exec_() == QDialog.Accepted:
            self.saveConfig()
    def about(self):
        w = PyTrailerAbout(self)
        w.exec_()

    def slotCreate(self, group):
        def slot():
            self.loadGroup(group)
        return slot

    def groupChange(self, button):
        self.loadGroup(str(button.text()))

    def unloadCurrentGroup(self):
        while not self.readAheadTaskQueue.empty():
            self.readAheadTaskQueue.get()

        widget = self.mainArea.takeAt(0)
        while widget != None:
            widget = widget.widget()
            self.movieDict.pop(widget.movie.title)
            widget.close()
            widget = self.mainArea.takeAt(0)

    def loadGroup(self, groupName):
        url = None
        for cat, catURL in categories:
            if cat == groupName:
                url = "http://trailers.apple.com%s" % catURL
                break

        self.unloadCurrentGroup()
        self.loadID = random.random()

        self.movieList = amt.getMoviesFromJSON(url)
        for i in range(len(self.movieList)):
            self.readAheadTaskQueue.put((i, self.movieList[i], self.loadID))
        filt = TrailerFilter()
        filters = pickle.loads(self.config.get("DEFAULT",'filters'))
        for trailerFilter in filters:
            filt.addCondition(trailerFilter)
        if len(filters) == 0:
            filt.addCondition(".*")

        for movie in self.movieList:
            w=MovieItemWidget(movie, filt, self.scrollArea)
            w.setVisible(False)
            w.downloadClicked.connect(self.downloadTrailer)
            self.movieDict[movie.title] = w
            self.mainArea.addWidget(w)

    def saveConfig(self):
        with open(self.configPath, 'wb') as configfile:
            self.config.write(configfile)

    def closeEvent(self, closeEvent):
        self.saveConfig()
        self.downloader.stop()
        for p in self.readAheadProcess:
            p.terminate()

    def refreshMovies(self):
        changed = False
        self.refreshDownloadStatus()
        while not self.readAheadDoneQueue.empty():
            i, updatedMovie, loadID = self.readAheadDoneQueue.get_nowait()
            if self.loadID != loadID:
                continue
            oldMovie = self.movieList[i]
            oldMovie.poster = updatedMovie.poster
            oldMovie.trailerLinks = updatedMovie.trailerLinks
            oldMovie.description = updatedMovie.description
            oldMovie.cached = True
            if self.movieDict.has_key(oldMovie.title):
                w = self.movieDict[oldMovie.title]
                if w is not None:
                    w.refresh()
                    w.setVisible(True)

    def refreshDownloadStatus(self):

        for i in self.trailerDownloadDict.keys():
            item = self.trailerDownloadDict[i]
            trailerName = item.url.split('/')[-1]
            statusText = None
            if item.status == DownloadStatus.IN_PROGRESS:
                statusText = "%d %% done" % item.percent
            elif item.status == DownloadStatus.DONE:
                statusText = "Done"
            elif item.status == DownloadStatus.ERROR:
                statusText = "Error"
            else:
                statusText = "Unknown"

            match = self.statusView.findItems(trailerName,Qt.MatchExactly)
            if match and len(match) > 0:
                match = match[0]
                match.setText(1, statusText)
            else:
                match = QTreeWidgetItem([trailerName, statusText])
                self.statusView.addTopLevelItem(match)


        if len(self.trailerDownloadDict.keys()) and not self.statusView.isVisible():
            self.statusView.setVisible(True)

    def downloadTrailer(self, url):
        self.trailerDownloadQueue.put((str(url),
                                      self.config.get("DEFAULT","downloadDir")))


class TrailerFilter(object):
    """Class to create filter so that we can show only
    some of the trailers (only HD/only 480p etc)
    """
    def __init__(self):
        self.conditions=[]

    def addCondition(self, regex):
        """Adds another condition that makes movie visible
        """
        self.conditions.append(re.compile(regex))

    def visible(self, trailerURL):
        """Class returns true if the trailer should be visible
        """
        for cond in self.conditions:
            if re.match(cond, trailerURL):
                return True
        return False

def movieReadAhead(taskQueue, doneQueue):
    """Function to be run in separate process,
    caching additional movie information
    """
    while True:
        i, movie, loadID = taskQueue.get()
        try:
            movie.poster
            movie.trailerLinks
            movie.description
            doneQueue.put((i, movie, loadID))
        except:
            raise


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = PyTrailerWidget()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
