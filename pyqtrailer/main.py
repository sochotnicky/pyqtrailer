
import sys
import os
import json
import pickle
import multiprocessing
import random
import subprocess
import locale
from time import mktime
import errno
try:
    import ConfigParser as configparser
except ImportError:
    import configparser as configparser

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import dateutil.parser as dparser


import pytrailer as amt
from .qtcustom import *
from .qtcustom import resources
from .downloader import TrailerDownloader, DownloadStatus


class PyTrailerWidget(QMainWindow):
    configPath = '%s/.pyqtrailer' % os.path.expanduser('~')
    cachePath = '%s/.pyqtrailer.cache' % os.path.expanduser('~')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        self.categories = [(self.tr('Just added'), '/trailers/home/feeds/just_added.json'),
                     (self.tr('Exclusive'), '/trailers/home/feeds/exclusive.json'),
                     (self.tr('Only HD'), '/trailers/home/feeds/just_hd.json'),
                     (self.tr('Most popular'), '/trailers/home/feeds/most_pop.json'),
                     (self.tr('Search'), '/trailers/home/scripts/quickfind.php?&q=')]
        self.config = configparser.SafeConfigParser({'downloadDir':'/tmp',
                                       'filters':json.dumps([y for x, y in PyTrailerSettings.filters]),
                                       'readAhead':'4',
                                       'parallelDownload':'2',
                                       'player':'mplayer -user-agent %%a %%u'})
        readAhead = int(self.config.get("DEFAULT","readAhead"))
        self.config.read(self.configPath)
        self.load_cache()
        self.movieDict = {}
        self.readAheadTaskQueue = multiprocessing.Queue()
        self.readAheadDoneQueue = multiprocessing.Queue()
        self.trailerDownloadQueue = multiprocessing.Queue()
        self.trailerDownloadDict = multiprocessing.Manager().dict()

        self.readAheadProcess = []
        for i in range(readAhead):
            p = multiprocessing.Process(target=PyTrailerWidget.movieReadAhead,
                        args=(self.readAheadTaskQueue,
                              self.readAheadDoneQueue,
                              self.movie_cache))
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
        self.list_loader = None
        self.refreshTimer.timeout.connect(self.refreshMovies)
        self.refreshTimer.start(1000)
        self.setWindowTitle(self.tr("PyTrailer - Apple Trailer Downloader"))

        centralWidget = QWidget()
        hbox = QHBoxLayout()
        group = QButtonGroup(hbox)
        group.setExclusive(True)
        for cat, url in self.categories:
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
        statusView.setHeaderLabels([self.tr("Trailer"),self.tr("Download status")])
        statusView.setVisible(False)
        statusView.setRootIsDecorated(False)
        statusView.setColumnWidth(0, self.width()-200)
        self.statusView = statusView

        self.loading = QLabel(self)
        self.loading.setSizePolicy(QSizePolicy.Expanding,
                              QSizePolicy.Expanding)
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setMinimumWidth(164)
        self.loading.setMinimumHeight(24)
        self.loading.setMaximumHeight(24)
        self.mov = QMovie(':/animation/loading', QByteArray(), self)
        self.loading.setMovie(self.mov)
        self.mov.start()
        self.loading.setVisible(True)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.loading)
        vbox.addWidget(scrollArea)
        vbox.addWidget(statusView)
        mlistLayout = QVBoxLayout()
        scrolledWidget.setLayout(mlistLayout)
        scrollArea.setWidget(scrolledWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumSize(QSize(400,350))

        self.mainArea = mlistLayout
        self.loadGroup(self.tr("Just added"))
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
        for cat, url in self.categories:
            movieMenu.addAction(cat, self.slotCreate(cat),
                                QKeySequence("F%d" % i))
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
        self.loadGroup(button.text())

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
        for cat, catURL in self.categories:
            if cat == groupName:
                url = "http://trailers.apple.com%s" % catURL
                break

        if groupName == self.tr("Search"):
            d = PyTrailerSearch(self)
            if d.exec_() == QDialog.Accepted:
                url = "%s%s" % (url, d.ui.lineEdit.text())
            else:
                return

        self.unloadCurrentGroup()
        self.loadID = random.random()
        self.loading.setVisible(True)
        self.list_loader , child_conn = multiprocessing.Pipe()
        self.list_loader_p = multiprocessing.Process(target=PyTrailerWidget.movieListLoader,
                                    args=(child_conn,url))
        self.list_loader_p.start()


    def saveConfig(self):
        with open(self.configPath, 'w') as configfile:
            self.config.write(configfile)

    def closeEvent(self, closeEvent):
        self.saveConfig()
        self.save_cache()
        self.downloader.stop()
        for p in self.readAheadProcess:
            p.terminate()

    def refreshMovies(self):
        if self.list_loader and self.list_loader.poll():
            self.movieList = self.list_loader.recv()
            self.display_group()
            self.list_loader_p.join()

        self.refreshDownloadStatus()
        while not self.readAheadDoneQueue.empty():
            i, updatedMovie, loadID = self.readAheadDoneQueue.get_nowait()
            if self.loadID != loadID:
                continue
            oldMovie = self.movieList[i]
            oldMovie.poster = updatedMovie.poster
            oldMovie.trailerLinks = updatedMovie.trailerLinks
            oldMovie.description = updatedMovie.description
            self.add_to_cache(oldMovie)
            if oldMovie.title in self.movieDict:
                w = self.movieDict[oldMovie.title]
                if w is not None:
                    w.refresh()
                    w.setVisible(True)
                else:
                    break

        # hide loading image when all movies are visible
        if self.readAheadTaskQueue.empty() and len(self.movieDict) != 0:
            allVisible = True
            for widget in self.movieDict:
                if not self.movieDict[widget].isVisible():
                    allVisible = False
                    break

            if allVisible:
                self.loading.setVisible(False)

    def display_group(self):
        self.list_loader = None
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

    def refreshDownloadStatus(self):

        for i in list(self.trailerDownloadDict.keys()):
            item = self.trailerDownloadDict[i]
            trailerName = item.url.split('/')[-1]
            statusText = None
            if item.status == DownloadStatus.IN_PROGRESS:
                statusText = "%d %% %s" % (item.percent, self.tr("done"))
            elif item.status == DownloadStatus.DONE:
                statusText = self.tr("Done")
            elif item.status == DownloadStatus.ERROR:
                statusText = self.tr("Error")
            elif item.status == DownloadStatus.WAITING:
                statusText = self.tr("Waiting")
            else:
                statusText = self.tr("Unknown")

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

    def add_to_cache(self, movie):
        latestUpdate = PyTrailerWidget.get_latest_trailer_date(movie)
        self.movie_cache[movie.baseURL] = (latestUpdate,
                                           movie.poster,
                                           movie.trailerLinks,
                                           movie.description)

    def load_cache(self):
        try:
            with open(self.cachePath,"rb") as f:
                self.movie_cache = pickle.load(f)
        except IOError as e:
            if e.errno == errno.ENOENT:
                self.movie_cache = {}
                self.movie_cache['last_update'] = 0
            else:
                raise

    def save_cache(self):
        with open(self.cachePath,"wb") as f:
            pickle.dump(self.movie_cache, f)

    @staticmethod
    def get_latest_trailer_date(movie):
        tsMax = 0
        for trailer in movie.trailers:
            locale.setlocale(locale.LC_ALL, "C")
            pdate = dparser.parse(trailer['postdate'])
            locale.resetlocale()
            ts = mktime(pdate.timetuple())
            if ts > tsMax:
                tsMax = ts
        return tsMax

    @staticmethod
    def movieReadAhead(taskQueue, doneQueue, cache):
        """Function to be run in separate process,
        caching additional movie information
        """
        while True:
            i, movie, loadID = taskQueue.get()
            try:
                latestUpdate = PyTrailerWidget.get_latest_trailer_date(movie)
                if movie.baseURL in cache and cache[movie.baseURL][0] >= latestUpdate:
                    cached_data = cache[movie.baseURL]
                    movie.poster = cached_data[1]
                    movie.trailerLinks = cached_data[2]
                    movie.description = cached_data[3]
                else:
                    movie.poster
                    movie.trailerLinks
                    movie.description
                doneQueue.put((i, movie, loadID))
            except:
                raise

    @staticmethod
    def movieListLoader(conn, url):
        conn.send(amt.getMoviesFromJSON(url))
        conn.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = PyTrailerWidget()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
