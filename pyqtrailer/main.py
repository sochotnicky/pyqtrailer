
import sys
import os
import json
import multiprocessing
import random
import subprocess
try:
    import ConfigParser as configparser
except ImportError:
    import configparser as configparser

from PyQt4.QtCore import *
from PyQt4.QtGui import *


from .qtcustom import *
import pytrailer as amt
from .downloader import TrailerDownloader, DownloadStatus

categories = [('Just added', '/trailers/home/feeds/just_added.json'),
              ('Exclusive', '/trailers/home/feeds/exclusive.json'),
              ('Only HD', '/trailers/home/feeds/just_hd.json'),
              ('Most popular', '/trailers/home/feeds/most_pop.json'),
              ('Search', '/trailers/home/scripts/quickfind.php?callback=searchCallback&q=')]


class PyTrailerWidget(QMainWindow):
    configPath = '%s/.pyqtrailer' % os.path.expanduser('~')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        self.config = configparser.SafeConfigParser({'downloadDir':'/tmp',
                                       'filters':json.dumps([y for x, y in PyTrailerSettings.filters]),
                                       'readAhead':'4',
                                       'parallelDownload':'2',
                                       'player':'mplayer -user-agent %%a %%u'})
        readAhead = int(self.config.get("DEFAULT","readAhead"))
        self.config.read(self.configPath)
        self.movieDict = {}
        self.readAheadTaskQueue = multiprocessing.Queue()
        self.readAheadDoneQueue = multiprocessing.Queue()
        self.trailerDownloadQueue = multiprocessing.Queue()
        self.trailerDownloadDict = multiprocessing.Manager().dict()

        self.readAheadProcess = []
        for i in range(readAhead):
            p = multiprocessing.Process(target=movieReadAhead,
                        args=(self.readAheadTaskQueue,
                              self.readAheadDoneQueue))
            p.start()
            self.readAheadProcess.append(p)

        self.downloader = TrailerDownloader(self.trailerDownloadQueue,
                               self.trailerDownloadDict,
                               int(self.config.get("DEFAULT","parallelDownload")))
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
        fileMenu = self.menuBar().addMenu(self.tr("&File"))

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
        try:
            filters = json.loads(self.config.get("DEFAULT","filters"))
        except ValueError:
            # we have old config load old style pickle
            import pickle
            filters = pickle.loads(self.config.get("DEFAULT","filters"))

        for movie in self.movieList:
            w=MovieItemWidget(movie, filters, self.scrollArea)
            w.setVisible(False)
            w.downloadClicked.connect(self.downloadTrailer)
            w.viewClicked.connect(self.viewTrailer)
            self.movieDict[movie.title] = w
            self.mainArea.addWidget(w)

    def saveConfig(self):
        with open(self.configPath, 'w') as configfile:
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
            if oldMovie.title in self.movieDict:
                w = self.movieDict[oldMovie.title]
                if w is not None:
                    w.refresh()
                    w.setVisible(True)

    def refreshDownloadStatus(self):

        for i in list(self.trailerDownloadDict.keys()):
            item = self.trailerDownloadDict[i]
            trailerName = item.url.split('/')[-1]
            statusText = None
            if item.status == DownloadStatus.IN_PROGRESS:
                statusText = "%d %% done" % item.percent
            elif item.status == DownloadStatus.DONE:
                statusText = "Done"
            elif item.status == DownloadStatus.ERROR:
                statusText = "Error"
            elif item.status == DownloadStatus.WAITING:
                statusText = "Waiting"
            else:
                statusText = "Unknown"

            match = self.statusView.findItems(trailerName,Qt.MatchExactly)
            if match and len(match) > 0:
                match = match[0]
                match.setText(1, statusText)
            else:
                match = QTreeWidgetItem([trailerName, statusText])
                self.statusView.addTopLevelItem(match)


        if len(list(self.trailerDownloadDict.keys())) and not self.statusView.isVisible():
            self.statusView.setVisible(True)

    def downloadTrailer(self, url):
        self.trailerDownloadQueue.put((str(url),
                                      self.config.get("DEFAULT","downloadDir")))
        self.trailerDownloadDict[str(url)] = DownloadStatus(str(url),
                           DownloadStatus.WAITING)
    def viewTrailer(self, url):
        player = self.config.get("DEFAULT","player").split(' ')
        for i in range(len(player)):
            if player[i] == '%a':
                player[i] = 'QuickTime/7.6.2 (qtver=7.6.2;os=Windows NT5.1 Service Pack 3)'
            elif player[i] == '%u':
                player[i] = url

        subprocess.Popen(player)


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
