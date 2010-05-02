
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
        titleLabel = QLabel("<h2>%s</h2>" % movie.title, self)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken);

        self.titlebox.addWidget(titleLabel)
        self.titlebox.addStretch(1)

        middleArea = QHBoxLayout()
        self.posterLabel = QLabel("<img src=""/>", self)
        self.posterLabel.setMinimumSize(QSize(134,193))
        self.posterLabel.setMaximumSize(QSize(134,193))

        mainArea = QVBoxLayout()
        self.mainArea = mainArea
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
        topLevelLayout.addStretch(1)
        self.setMinimumSize(400,150)
        self.setLayout(topLevelLayout)

    def refresh(self):
        movie = self.movie

        posterImage = QImage()
        posterImage.loadFromData(movie.poster)
        self.posterLabel.setPixmap(QPixmap.fromImage(posterImage))

        self.downloadButtons = QButtonGroup()
        self.downloadButtons.buttonClicked.connect(self.downloadClicked)
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

    def downloadClicked(self, button):
        id = self.downloadButtons.id(button)
        print id
        os.chdir('/data/downloads/torrents')
        subprocess.Popen(['wget','-U','QuickTime/7.6.2 (qtver=7.6.2;os=Windows NT 5.1Service Pack 3)', self.movie.trailerLinks[id]])


