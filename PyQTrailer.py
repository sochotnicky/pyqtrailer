#!/usr/bin/python

import sys
import os
import pickle
from multiprocessing import Process, Queue
import ConfigParser as configparser

from PyQt4.QtCore import *
from PyQt4.QtGui import *


from qtcustom import *
import amt


categories = {'Just added':'/trailers/home/feeds/just_added.json',
              'Exclusive':'/trailers/home/feeds/exclusive.json',
              'Only HD':'/trailers/home/feeds/just_hd.json',
              'Most popular':'/trailers/home/feeds/most_pop.json',
              'Search':'/trailers/home/scripts/quickfind.php?callback=searchCallback&q='}


class PyTrailerWidget(QMainWindow):
    configPath = '%s/.pyqtrailer' % os.path.expanduser('~')
    
    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        READ_AHEAD_PROC=4
        self.config = configparser.SafeConfigParser({'downloadDir':'/tmp'})
        self.config.read(self.configPath)
        self.movieDict = {}
        self.readAheadTaskQueue = Queue()
        self.readAheadDoneQueue = Queue()

        self.readAheadProcess = []
        for i in range(READ_AHEAD_PROC):
            p = Process(target=movieReadAhead,
                        args=(self.readAheadTaskQueue,
                              self.readAheadDoneQueue))
            p.start()
            self.readAheadProcess.append(p)

        self.init_widget()
        self.init_menus()

    def init_widget(self):

        self.refreshTimer = QTimer(self)
        self.refreshTimer.timeout.connect(self.refreshMovies)
        self.refreshTimer.start(1000)
        self.setWindowTitle(self.tr("PyTrailer - Apple Trailer Downloader"))

        hbox = QHBoxLayout()
        group = QButtonGroup(hbox)
        group.setExclusive(True)
        for cat in categories.keys():
            but = QPushButton(cat, self)
            but.setCheckable(True)
            group.addButton(but)
            hbox.addWidget(but)

        group.buttonClicked.connect(self.groupChange)

        self.scrollArea = QScrollArea(self)
        scrollArea = self.scrollArea
        self.scrolledWidget = QWidget(self)
        scrolledWidget = self.scrolledWidget
        self.hackTmp = scrolledWidget
        scrollArea.setSizePolicy(QSizePolicy.Ignored,
                QSizePolicy.Ignored)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(scrollArea)
        mlistLayout = QVBoxLayout()
        scrolledWidget.setLayout(mlistLayout)
        scrollArea.setWidget(scrolledWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumSize(QSize(400,150))
        self.mainArea = mlistLayout
        self.loadGroup("Just added")



        self.setLayout(vbox)
        self.setCentralWidget(scrollArea)

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
        for cat in categories.keys():
            movieMenu.addAction(self.tr(cat), self.slotCreate(cat),
                                QKeySequence(self.tr("F%d" % i,
                                "Movies|%s" % cat)))
            i = i + 1

    def settings(self):
        d = PyTrailerSettings(self.config)
        if d.exec_() == QDialog.Accepted:
            self.config.set("DEFAULT","downloadDir",str(d.downloadPath.text()))
            self.saveConfig()

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
        self.unloadCurrentGroup()

        url = "http://trailers.apple.com%s" % categories[groupName]
        self.movieList = amt.getMoviesFromJSON(url)
        for i in range(len(self.movieList)):
            self.readAheadTaskQueue.put((i, self.movieList[i]))

        for movie in self.movieList:
            w=MovieItemWidget(movie, self.scrollArea)
            self.movieDict[movie.title] = w
            self.mainArea.addWidget(w)
    def saveConfig(self):
        with open(self.configPath, 'wb') as configfile:
            self.config.write(configfile)

    def closeEvent(self, closeEvent):
        self.saveConfig()
        for p in self.readAheadProcess:
            p.terminate()

    def refreshMovies(self):
        changed = False
        while not self.readAheadDoneQueue.empty():
            i, updatedMovie = self.readAheadDoneQueue.get_nowait()
            oldMovie = self.movieList[i]
            oldMovie.poster = updatedMovie.poster
            oldMovie.trailerLinks = updatedMovie.trailerLinks
            oldMovie.cached = True
            if self.movieDict.has_key(oldMovie.title):
                w = self.movieDict[oldMovie.title]
                if w is not None:
                    w.refresh()


def movieReadAhead(taskQueue, doneQueue):
    while True:
        i, movie = taskQueue.get()
        try:
            movie.poster
            movie.trailerLinks
            doneQueue.put((i, movie))
        except:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = PyTrailerWidget()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
