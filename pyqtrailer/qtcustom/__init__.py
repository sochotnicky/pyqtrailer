import json
import locale
import re

from PyQt4.QtCore import *
from PyQt4.QtGui import *

try:
    from PyQt4.QtCore import QString
except ImportError:
    # we are using Python3 so QString is not defined
    QString = str

from .settings_ui import Ui_SettingsDialog
from .about_ui import Ui_AboutDialog
from .search_ui import Ui_Search
from .. import version
__version__ = version.__version__
import dateutil.parser as dparser

class MovieItemWidget(QFrame):
    def __init__(self, movie, trailerFilters, *args):
        QWidget.__init__(self, *args)

        self.movie = movie
        self.filters = trailerFilters

        self.titlebox = QHBoxLayout()
        releaseDate=None
        if hasattr(movie, "releasedate"):
            locale.setlocale(locale.LC_ALL, "C")
            releaseDate = dparser.parse(movie.releasedate)
            locale.resetlocale()
            releaseDate = releaseDate.strftime("%x")
        else:
            releaseDate = self.tr("Unknown")
        titleLabel = QLabel("<h2>%s</h2> (%s %s)" % (movie.title, self.tr("Release date:"), releaseDate), self)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken);

        self.titlebox.addWidget(titleLabel)
        self.titlebox.addStretch(1)

        middleArea = QHBoxLayout()
        self.posterLabel = QLabel("<img src=""/>", self)
        self.posterLabel.setMinimumSize(QSize(134,193))
        self.posterLabel.setMaximumSize(QSize(134,193))

        mainArea = QVBoxLayout()
        self.mainArea = mainArea
        genre = QLabel("<b>%s</b>%s" % (self.tr("Genre(s): "),
                                          self.__get_movie_info(movie, "genre", True)))
        mainArea.addWidget(genre)

        studio = QLabel("<b>%s</b>%s" % (self.tr("Studio: "),
                                           self.__get_movie_info(movie, "studio")))
        mainArea.addWidget(studio)

        directors = QLabel("<b>%s</b>%s" % (self.tr("Director(s): "),
                                              self.__get_movie_info(movie, "directors")))
        mainArea.addWidget(directors)

        actors = QLabel("<b>%s</b>%s" % (self.tr("Actors: "),
                                               self.__get_movie_info(movie, "actors", True)))
        mainArea.addWidget(actors)
        actors.setWordWrap(True)
        mainArea.addStretch(1)

        middleArea.addWidget(self.posterLabel)
        middleArea.addLayout(mainArea)


        topLevelLayout = QVBoxLayout()
        topLevelLayout.addLayout(self.titlebox)
        topLevelLayout.addLayout(middleArea)
        self.setMinimumSize(400,150)
        self.setLayout(topLevelLayout)

    def __get_movie_info(self, movie, info, join=False):
        ret = self.tr("Unknown")
        if hasattr(movie, info):
            if join:
                ret = ", ".join(getattr(movie, info))
            else:
                ret = getattr(movie, info)
        return ret

    def refresh(self):

        movie = self.movie

        self.button_mapping = {}
        posterImage = QImage()
        posterImage.loadFromData(movie.poster)
        self.posterLabel.setPixmap(QPixmap.fromImage(posterImage))

        self.downloadButtons = QButtonGroup()
        self.downloadButtons.buttonClicked.connect(self.download)
        self.viewButtons = QButtonGroup()
        self.viewButtons.buttonClicked.connect(self.view)
        links = 0
        for trailerName in movie.trailerLinks:
            trailerURLS = movie.trailerLinks[trailerName]
            match = 0
            for tf in self.filters:
                cond = re.compile(tf)
                for url in trailerURLS:
                    if re.match(cond, url):
                        self._add_buttons(trailerName, url, links)
                        links = links + 1
                        match = 1
                        break
                if match == 1:
                    break


        desc = QLabel(movie.description)
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        self.layout().addWidget(desc)

    def _add_buttons(self, trailerName, trailerLink, ids):
        trailerName = "%s (%s)" % (trailerName,
                                   PyTrailerSettings.get_quality_from_url(trailerLink))
        lab = QLabel('<a href="%s">%s</a>' % (trailerLink, trailerName), self)
        hbox= QHBoxLayout()
        button=QPushButton(self.tr("Download"))
        self.downloadButtons.addButton(button, ids)
        self.button_mapping[ids] = trailerLink
        hbox.addStretch(1)
        hbox.addWidget(lab)
        hbox.addWidget(button)
        button=QPushButton(self.tr("View"))
        self.viewButtons.addButton(button, ids)
        hbox.addWidget(button)
        self.mainArea.addLayout(hbox)

    downloadClicked = pyqtSignal((QString, ))
    viewClicked = pyqtSignal((QString, ))

    def download(self, button):
        id = self.downloadButtons.id(button)
        self.downloadClicked.emit(self.button_mapping[id])

    def view(self, button):
        id = self.viewButtons.id(button)
        self.viewClicked.emit(self.button_mapping[id])


class PyTrailerSettings(QDialog):
    filters = [('320x180',r'.*h320\.mov$'),
               ('480x204',r'.*h480\.mov$'),
               ('640x360',r'.*h640w\.mov$'),
               ('480p',r'.*480p\.mov$'),
               ('720p',r'.*720p\.mov$'),
               ('1080p',r'.*1080p\.mov$')]

    def __init__(self, config):
        QDialog.__init__(self)
        self.config = config
        self.ui = Ui_SettingsDialog()
        self.ui.setupUi(self)
        self.ui.downloadPath.setText(config.get("DEFAULT","downloadDir"))
        self.ui.spinReadAhead.setValue(int(config.get("DEFAULT","readAhead")))
        self.ui.spinParallelDownload.setValue(int(config.get("DEFAULT","parallelDownload")))

        self.ui.browseButton.clicked.connect(self.browseDir)
        self.ui.qualityUp.clicked.connect(self.filter_up)
        self.ui.qualityDown.clicked.connect(self.filter_down)

        self.ui.playerCommand.setText(config.get("DEFAULT","player"))

        activeFilters = json.loads(config.get("DEFAULT","filters"))
        self.ui.filterList.clear()
        added = []
        for filt in activeFilters:
            for fn, fregex in self.filters:
                if fregex  == filt:
                    self.ui.filterList.addItem(fn)
                    added.append(fn)

        for filt in self.filters:
            if filt[0] not in added:
                self.ui.filterList.addItem(filt[0])
                added.append(filt[0])

    def filter_up(self):
        currentRow = self.ui.filterList.currentRow()
        if currentRow == 0:
            return

        item = self.ui.filterList.takeItem(currentRow)
        self.ui.filterList.insertItem(currentRow-1, item)
        self.ui.filterList.setCurrentRow(currentRow-1)

    def filter_down(self):
        currentRow = self.ui.filterList.currentRow()
        if currentRow == self.ui.filterList.count()-1:
            return

        item = self.ui.filterList.takeItem(currentRow)
        self.ui.filterList.insertItem(currentRow+1, item)
        self.ui.filterList.setCurrentRow(currentRow+1)

    def accept(self):
        self.config.set("DEFAULT","downloadDir",
                        str(self.ui.downloadPath.text()))
        playerStr = str(self.ui.playerCommand.text().replace('%','%%'))
        self.config.set("DEFAULT","player", playerStr)
        activeFilters = []
        for i in range(self.ui.filterList.count()):
            itemWidget = self.ui.filterList.takeItem(0)
            filterName = str(itemWidget.text())
            for fn, fregex in self.filters:
                if fn == filterName:
                    activeFilters.append(fregex)
        self.config.set("DEFAULT","filters", json.dumps(activeFilters))
        self.config.set("DEFAULT","readAhead", str(self.ui.spinReadAhead.value()))
        self.config.set("DEFAULT","parallelDownload", str(self.ui.spinParallelDownload.value()))
        QDialog.accept(self)

    def browseDir(self):
        directory = QFileDialog.getExistingDirectory(self,
                                                     QString(),
                                                     self.config.get("DEFAULT",
                                                                     "downloadDir"))
        if directory:
            self.ui.downloadPath.setText(directory)

    @staticmethod
    def get_quality_from_url(url):
        for fn, fregex in PyTrailerSettings.filters:
            if re.match(fregex, url):
                return fn
        return self.tr("Unknown quality")

class PyTrailerAbout(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)
        self._main  = parent
        self.ui.label_version.setText(__version__)
        self.connect(self.ui.buttonClose, SIGNAL("clicked(bool)"), self.close)

class PyTrailerSearch(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.ui = Ui_Search()
        self.ui.setupUi(self)
        self._main  = parent
