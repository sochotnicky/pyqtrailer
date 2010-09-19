from distutils.core import setup
import pyqtrailer
import subprocess

for ui in ['pyqtrailer/qtcustom/settings.ui','pyqtrailer/qtcustom/about.ui']:
    out = ui.replace('.ui','_ui.py')
    command = ["pyuic4","-o",out, ui]
    subprocess.Popen(command)
    print "run %s" % command

setup(name='pyqtrailer',
      version=pyqtrailer.__version__,
      description='PyQt4 application to download trailers from www.apple.com/trailers',
      author='Stanislav Ochotnicky',
      author_email='sochotnicky@gmail.com',
      url='http://code.google.com/p/pyqtrailer',
      requires=["pytrailer"],
      install_requires=['pytrailer>=0.3',"python-dateutil >= 1.5"],
      classifiers=['Development Status :: 4 - Beta',
                   'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
                   'Programming Language :: Python :: 2.6',
                   'Topic :: Software Development :: User Interfaces',
                   'Topic :: Multimedia :: Video'],
      keywords="movie trailer apple module pyqt qt4",
      license="GPLv3",
      platforms=["any"],
      packages=["pyqtrailer",
                "pyqtrailer.qtcustom"],
      scripts=["scripts/pyqtrailer"],
     )
