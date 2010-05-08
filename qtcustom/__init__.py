import subprocess
import os
import time
import locale

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class CategoryPushButton(QPushButton):
    def __init__(self, text, parent, jsonLink):
        QPushButton.__init__(self, text, parent)
        self.jsonLink = jsonLink

class MovieItemWidget(QFrame):
    def __init__(self, movie, *args):
        QWidget.__init__(self, *args)

        self.movie = movie

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
        if not self.isVisible():
            return

        movie = self.movie

        posterImage = QImage()
        posterImage.loadFromData(movie.poster)
        self.posterLabel.setPixmap(QPixmap.fromImage(posterImage))

        self.downloadButtons = QButtonGroup()
        self.downloadButtons.buttonClicked.connect(self.download)
        links = 0
        for trailerLink in movie.trailerLinks:
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

        hbox = QHBoxLayout()
        hbox.addWidget(label)
        hbox.addWidget(self.downloadPath)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok
                                      | QDialogButtonBox.Cancel);

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"));
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"));
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(buttonBox)
        self.setLayout(vbox)
