import pickle
import time
import locale

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class CategoryPushButton(QPushButton):
    def __init__(self, text, parent, jsonLink):
        QPushButton.__init__(self, text, parent)
        self.jsonLink = jsonLink

class MovieItemWidget(QFrame):
    def __init__(self, movie, trailerFilter, *args):
        QWidget.__init__(self, *args)

        self.movie = movie
        self.filter = trailerFilter

        self.titlebox = QHBoxLayout()
        locale.setlocale(locale.LC_ALL, "C")
        releaseDate=None
        if movie.releasedate:
            releaseDate = time.strptime(movie.releasedate, "%a, %d %b %Y %H:%M:%S +0000")
            locale.resetlocale()
            releaseDate = time.strftime("%x", releaseDate)
        titleLabel = QLabel("<h2>%s</h2> (Release date: %s)" %
        (movie.title, releaseDate), self)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken);

        self.titlebox.addWidget(titleLabel)
        self.titlebox.addStretch(1)

        middleArea = QHBoxLayout()
        self.posterLabel = QLabel("<img src=""/>", self)
        self.posterLabel.setMinimumSize(QSize(134,193))
        self.posterLabel.setMaximumSize(QSize(134,193))

        mainArea = QVBoxLayout()
        self.mainArea = mainArea
        if movie.genre:
            genStr = ", ".join(movie.genre)
        else:
            genStr = "Unknown"
        genre = QLabel("<b>Genre(s): </b>%s" % genStr)
        mainArea.addWidget(genre)
        studio = QLabel("<b>Studio: </b>%s" % movie.studio)
        mainArea.addWidget(studio)
        directors = QLabel("<b>Director(s): </b>%s" % ", ".join([movie.directors]))
        mainArea.addWidget(directors)
        actors = QLabel("<b>Actors: </b>%s" % ", ".join(movie.actors))
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

    def refresh(self):

        movie = self.movie

        posterImage = QImage()
        posterImage.loadFromData(movie.poster)
        self.posterLabel.setPixmap(QPixmap.fromImage(posterImage))

        self.downloadButtons = QButtonGroup()
        self.downloadButtons.buttonClicked.connect(self.download)
        links = 0
        for trailerLink in movie.trailerLinks:
            if not self.filter.visible(trailerLink):
                links = links + 1
                continue
            label = '%s' % trailerLink.split('/')[-1]
            label = label[:label.rindex('.mov')]
            lab = QLabel('<a href="%s">%s</a>' % (trailerLink, label),self)
            hbox= QHBoxLayout()
            button=QPushButton("Download")
            self.downloadButtons.addButton(button, links)
            hbox.addStretch(1)
            hbox.addWidget(lab)
            hbox.addWidget(button)
            button=QPushButton("View")
            hbox.addWidget(button)
            self.mainArea.addLayout(hbox)
            links = links + 1
        desc = QLabel(movie.description)
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        self.layout().addWidget(desc)

    downloadClicked = pyqtSignal((QString, ))

    def download(self, button):
        id = self.downloadButtons.id(button)
        self.downloadClicked.emit(self.movie.trailerLinks[id])

class PyTrailerSettings(QDialog):
    def __init__(self, config):
        QDialog.__init__(self)
        self.config = config
        label = QLabel(self.tr("&Download path"))
        self.downloadPath = QLineEdit(self)
        self.downloadPath.setText(config.get("DEFAULT","downloadDir"))
        label.setBuddy(self.downloadPath)

        browseBut = QPushButton(self.tr("&Browse"))
        browseBut.clicked.connect(self.browseDir)

        hbox = QHBoxLayout()
        hbox.addWidget(label)
        hbox.addWidget(self.downloadPath)
        hbox.addWidget(browseBut)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        hbox = QHBoxLayout()
        self.filters = [('all','.*mov.*'),
                   ('320x180',r'.*h320\.mov.*'),
                   ('480x204',r'.*h480\.mov.*'),
                   ('640x360',r'.*h640\.mov.*'),
                   ('480p',r'.*480p\.mov.*'),
                   ('720p',r'.*720p\.mov.*'),
                   ('1080p',r'.*1080p\.mov.*')]
        activeFilters = pickle.loads(config.get("DEFAULT","filters"))
        filterLayout = QVBoxLayout()
        filterGroup = QGroupBox(self.tr("Trailer quality filter"))
        filterGroup.setLayout(filterLayout)
        vbox.addWidget(filterGroup)
        self.filterButtons = []
        for qual, filt in self.filters:
            active = False
            if filt in activeFilters:
                active = True
            option = QCheckBox(qual)
            option.setChecked(active)
            self.filterButtons.append(option)
            filterLayout.addWidget(option)

        self.filterButtons[0].clicked.connect(self.refreshFilters)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok
                                      | QDialogButtonBox.Cancel);

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"));
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"));
        vbox.addWidget(buttonBox)
        self.setLayout(vbox)
        self.refreshFilters()

    def refreshFilters(self):
        for button in self.filterButtons[1:]:
            button.setEnabled(not self.filterButtons[0].isChecked())


    def accept(self):
        self.config.set("DEFAULT","downloadDir",
                        str(self.downloadPath.text()))
        activeFilters = []
        ind = 0
        for button in self.filterButtons:
            if button.isChecked():
                activeFilters.append(self.filters[ind][1])
            ind = ind + 1
        self.config.set("DEFAULT","filters",pickle.dumps(activeFilters))
        QDialog.accept(self)

    def browseDir(self):
        directory = QFileDialog.getExistingDirectory(self,
                                                     QString(),
                                                     self.config.get("DEFAULT",
                                                                     "downloadDir"))
        if directory:
            self.downloadPath.setText(directory)


