import sys
import os
import pickle
import time
from multiprocessing import Process, Queue
import subprocess

from PyQt4.QtCore import *
from PyQt4.QtGui import *


from qtcustom import *
import amt


categories = {'Just added':'/trailers/home/feeds/just_added.json',
              'Exclusive':'/trailers/home/feeds/exclusive.json',
              'Only HD':'/trailers/home/feeds/just_hd.json',
              'Most popular':'/trailers/home/feeds/most_pop.json',
              'Search':'/trailers/home/scripts/quickfind.php?callback=searchCallback&q='}


class PyTrailerWidget(QWidget):
    def __init__(self, *args):
        QWidget.__init__(self, *args)
        READ_AHEAD_PROC=4
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

    def init_widget(self):

        self.refreshTimer = QTimer(self)
        self.refreshTimer.timeout.connect(self.refreshMovies)
        self.refreshTimer.start(500)
        self.setWindowTitle("PyTrailer - Apple Trailer Downloader")

        hbox = QHBoxLayout()
        group = QButtonGroup(hbox)
        group.setExclusive(True)
        for cat in categories.keys():
            but = QPushButton(cat, self, categories[cat])
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


        shortcut = QShortcut(QKeySequence(self.tr("Ctrl+Q", "File|Quit")),
                          self);
        self.connect(shortcut, SIGNAL('activated()'), SLOT('close()'))

        self.setLayout(vbox)


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

    def closeEvent(self, closeEvent):
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
