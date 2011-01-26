
import sys
import os
import json
import pickle
import multiprocessing
import random
import subprocess
import errno
import traceback
import socket
import signal

try:
    import ConfigParser as configparser
    from urllib2 import URLError
except ImportError:
    from urllib.error import URLError
    import configparser as configparser

from PyQt4.QtCore import *
from PyQt4.QtGui import *



import pytrailer as amt
from .qtcustom import *
from .qtcustom import resources
from .downloader import TrailerDownloader, DownloadStatus
from logger import log

term_closing = 0


class PyTrailerWidget(QMainWindow):
    """Main PyQTrailer window. This is where it all starts"""

    configPath = '%s/.pyqtrailer' % os.path.expanduser('~')
    cachePath = '%s/.pyqtrailer.cache' % os.path.expanduser('~')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        log.debug("main window initialization starting")
        # these are all categories apple is providing for now
        self.categories = [(self.tr('Just added'), '/trailers/home/feeds/just_added.json'),
                     (self.tr('Exclusive'), '/trailers/home/feeds/exclusive.json'),
                     (self.tr('Only HD'), '/trailers/home/feeds/just_hd.json'),
                     (self.tr('Most popular'), '/trailers/home/feeds/most_pop.json'),
                     (self.tr('Search'), '/trailers/home/scripts/quickfind.php?&q=')]

        # pick sane defaults
        self.config = configparser.SafeConfigParser({'downloadDir':'/tmp',
                                       'filters':json.dumps([y for x, y in PyTrailerSettings.filters]),
                                       'readAhead':'4',
                                       'parallelDownload':'2',
                                       'player':'mplayer -user-agent %%a %%u'})

        log.info("settings loaded: %s" % self.config.items("DEFAULT"))
        # run initializations
        self.player_proc = None
        self.list_loader = None
        self.list_loader_p = None
        self.movieDict = {}
        self.config.read(self.configPath)
        self.load_cache()
        self.init_preloaders()
        self.init_widget()
        self.init_menus()
        self.downloader.start()
        signal.signal(signal.SIGTERM, PyTrailerWidget.term_handler)
        signal.signal(signal.SIGINT, PyTrailerWidget.term_handler)
        log.debug("main window initialization done")

    def init_widget(self):
        """Initialize main child widgets, layouts etc."""

        self.refreshTimer = QTimer(self)
        self.refreshTimer.timeout.connect(self.refresh_wrapper)
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

        group.buttonClicked.connect(self.group_change)

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
        self.load_group(self.tr("Just added"))
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
            movieMenu.addAction(cat, self.slot_create(cat),
                                QKeySequence("F%d" % i))
            i = i + 1
        aboutMenu = self.menuBar().addMenu(self.tr("&Help"))

        aboutMenu.addAction(self.tr("&About"),
                            self.about,
                            QKeySequence(self.tr("Ctrl+A",
                                                 "Help|About PyQTrailer")))

    def init_preloaders(self):
        """Start all preloading processes and prepare data for them"""

        # taskQueue - trailers to be cached go there
        self.readAheadTaskQueue = multiprocessing.Queue()
        # doneQueue - cached trailes come from there
        self.readAheadDoneQueue = multiprocessing.Queue()

        # trailers to be downloaded are put there
        self.trailerDownloadQueue = multiprocessing.Queue()

        # this is a url:DownloadStatus dictionary
        self.trailerDownloadDict = multiprocessing.Manager().dict()

        self.readAheadProcess = []
        readAhead = int(self.config.get("DEFAULT","readAhead"))
        for i in range(readAhead):
            p = multiprocessing.Process(target=PyTrailerWidget.movie_readahead,
                        args=(self.readAheadTaskQueue,
                              self.readAheadDoneQueue,
                              self.movie_cache))
            p.start()
            self.readAheadProcess.append(p)

        self.downloader = TrailerDownloader(self.trailerDownloadQueue,
                               self.trailerDownloadDict,
                               int(self.config.get("DEFAULT","parallelDownload")))

    def slot_create(self, group):
        """This meta-function is used to create anonymous slot for each
        trailer group."""
        def slot():
            self.load_group(group)
        return slot

    def settings(self):
        d = PyTrailerSettings(self.config)
        if d.exec_() == QDialog.Accepted:
            self.save_config()

    def about(self):
        w = PyTrailerAbout(self)
        w.exec_()


    def group_change(self, button):
        self.load_group(button.text())

    def unload_current_group(self):
        """Current trailer groups gets unloaded and preloader
        processes stopped
        """
        log.debug("unloading previous group")
        while not self.readAheadTaskQueue.empty():
            self.readAheadTaskQueue.get()

        if self.list_loader:
            self.list_loader.close()
            self.list_loader = None

        if self.list_loader_p:
            self.list_loader_p.terminate()

        # remove trailer widgets from main area
        widget = self.mainArea.takeAt(0)
        while widget != None:
            widget = widget.widget()
            self.movieDict.pop(widget.movie.title)
            widget.close()
            widget = self.mainArea.takeAt(0)

    def load_group(self, groupName):
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

        self.unload_current_group()
        log.debug("loading group %s" % groupName)
        # loadID is used to identify what group task belonged to
        # we can use it to make sure we don't display trailers from
        # different group after being cached
        self.loadID = random.random()
        self.loading.setVisible(True)

        # run loading in separate process
        self.list_loader , child_conn = multiprocessing.Pipe()
        self.list_loader_p = multiprocessing.Process(target=PyTrailerWidget.movielist_loader,
                                    args=(child_conn,url))
        self.list_loader_p.start()


    def save_config(self):
        log.debug("saving config file")
        with open(self.configPath, 'w') as configfile:
            self.config.write(configfile)

    def closeEvent(self, close_event):
        self.downloader.stop()
        for p in self.readAheadProcess:
            p.terminate()
        self.list_loader_p.terminate()
        if self.player_proc:
            self.player_proc.poll()
            if self.player_proc.returncode is None:
                self.player_proc.terminate()
        self.save_config()
        self.save_cache()
        log.debug("closing application")

    def refresh_wrapper(self):
        if not term_closing:
            self.refresh_movies()
        else:
            self.refreshTimer.stop()
            self.close()

    def refresh_movies(self):
        # if we are loading new group and movie list is ready, get it
        if self.list_loader and self.list_loader.poll():
            exception, self.movieList = self.list_loader.recv()
            if exception:
                self.report_network_problem(exception)
            else:
                self.display_group()
            self.list_loader_p.join()
        # let's refresh status of trailer downloads
        self.refresh_download_status()

        # now to refreshing trailer widgets when posters, descriptions
        # and trailer links have been cached
        while not self.readAheadDoneQueue.empty():
            i, updatedMovie, loadID = self.readAheadDoneQueue.get_nowait()
            if self.loadID != loadID:
                # this means the cached movie comes from previous
                # group (we must have changed group recently)
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
        """Makes the hard work to prepare current group for being
        displayed

        adds tasks to readahead process and creates widgets"""
        self.list_loader = None
        for i in range(len(self.movieList)):
            self.readAheadTaskQueue.put((i, self.movieList[i], self.loadID))

        try:
            filters = json.loads(self.config.get("DEFAULT","filters"))
        except ValueError:
            # we have old config load old style pickle
            import pickle
            filters = pickle.loads(self.config.get("DEFAULT","filters"))

        # we create widgets but hide them until they are cached
        for movie in self.movieList:
            w=MovieItemWidget(movie, filters, self.scrollArea)
            w.setVisible(False)
            w.downloadClicked.connect(self.download_trailer)
            w.viewClicked.connect(self.view_trailer)
            self.movieDict[movie.title] = w
            self.mainArea.addWidget(w)

    def refresh_download_status(self):
        """Makes sure download status is up to date
        """
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

        if self.player_proc:
            self.player_proc.poll()
            ret = self.player_proc.returncode
            if ret and ret != 0:
                log.error("player return code was non-null. Player output:")
                log.error(self.player_proc.stderr.read())
                QMessageBox.critical(self,
                                self.tr("Player error"),
                                self.tr(
"""Player indicates error while playing selected trailer.
Please verify player configuration is correct.
For player error output see log file
"""))
                self.player_proc = None


    def download_trailer(self, url):
        """Adds appropriate tasks to download trailer and sets initial
        DownloadStatus"""
        log.info("initializing download of %s" % url)
        self.trailerDownloadQueue.put((str(url),
                                      self.config.get("DEFAULT","downloadDir")))
        self.trailerDownloadDict[str(url)] = DownloadStatus(str(url),
                           DownloadStatus.WAITING)

    def view_trailer(self, url):
        player = self.config.get("DEFAULT","player").split(' ')
        for i in range(len(player)):
            if player[i] == '%a':
                player[i] = 'QuickTime/7.6.2 (qtver=7.6.2;os=Windows NT5.1 Service Pack 3)'
            elif player[i] == '%u':
                player[i] = url

        log.info("running player: %s" % player)
        try:
            self.player_proc = subprocess.Popen(player, stderr=subprocess.PIPE)
        except OSError as e:
            log.error("player could not be executed")
            log.error(traceback.format_exc())
            if e.errno == errno.ENOENT:
                # player doesn't exist
                QMessageBox.critical(self,
                                self.tr("Player executable not found"),
                                self.tr("Player could not be run.\nPlease verify player configuration is correct"))
            else:
                QMessageBox.critical(self,
                                self.tr("Player execution failure"),
                                self.tr("Unknown error while running player."))




    def add_to_cache(self, movie):
        """Adds movie to disk cache"""
        log.debug("adding movie to cache: %s" % movie.title)
        latestUpdate = movie.get_latest_trailer_date()
        self.movie_cache[movie.baseURL] = (latestUpdate,
                                           movie.poster,
                                           movie.trailerLinks,
                                           movie.description)

    def load_cache(self):
        """Loads trailer info cache from disk"""
        log.debug("loading cache from disk")
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
        """Saves trailer info cache to disk"""
        log.debug("saving cache to disk")
        with open(self.cachePath,"wb") as f:
            pickle.dump(self.movie_cache, f)

    def report_network_problem(self, exception):
        QMessageBox.critical(self,
                             self.tr("Network error"),
                             self.tr(
"""There was a network problem when downloading movie list.
Please check your network settings.
"""))


    @staticmethod
    def movie_readahead(taskQueue, doneQueue, cache):
        """Function to be run in separate process,
        caching additional movie information
        """
        while True:
            try:
                i, movie, loadID = taskQueue.get()
                log.debug("loading information about movie %s" % movie.title)
                latestUpdate = movie.get_latest_trailer_date()
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
            except socket.error as e:
                log.error("network problem error while loading movie information: %s" % e)
                log.error(traceback.format_exc())
            except KeyboardInterrupt:
                log.debug("keyboard interrupt. stopping movie readahead")
                return
            except:
                log.error("uncaught exception ocurred while doing readahead. Please report this!")
                log.error(traceback.format_exc())
                raise

    @staticmethod
    def movielist_loader(conn, url):
        """Function to be run in a separate process. It will send
        movie list through pipe. Use poll() to verify that data is ready.
        """
        try:
            log.info("getting movie list from %s" % url)
            movies = amt.getMoviesFromJSON(url)
            conn.send((None, movies))
            conn.close()
        except URLError as e:
            log.error("network problem error while loading movie list: %s" % e)
            log.error(traceback.format_exc())
            conn.send((e, None))
        except socket.error as e:
            log.error("network problem error while loading movie list: %s" % e)
            log.error(traceback.format_exc())
            conn.send((e, None))
        except Exception as e:
            log.error("uncaught exception ocurred while loading movie list. Please report this!")
            log.error(traceback.format_exc())
            conn.send((e, None))


    @staticmethod
    def term_handler(signum, frame):
        """Handles closing of main process."""
        global term_closing
        term_closing = 1
