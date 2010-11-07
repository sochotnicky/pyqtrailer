from distutils.command.build_py import build_py as _build_py
from distutils.core import setup
import pyqtrailer
import subprocess
import sys

class build_py(_build_py):
    uis = ["%s/pyqtrailer/qtcustom/settings.ui" % sys.path[0],
           "%s/pyqtrailer/qtcustom/about.ui" % sys.path[0],
           "%s/pyqtrailer/qtcustom/search.ui" % sys.path[0]]

    def run(self):
        for ui in self.uis:
            out = ui.replace('.ui','_ui.py')
            command = ["pyuic4","-o",out, ui]
            subprocess.Popen(command)
            self.byte_compile(out)
        _build_py.run(self)


setup(name='pyqtrailer',
      version=pyqtrailer.__version__,
      description='PyQt4 application to download trailers from www.apple.com/trailers',
      author='Stanislav Ochotnicky',
      author_email='sochotnicky@gmail.com',
      url='http://github.com/sochotnicky/pyqtrailer',
      requires=["pytrailer"],
      install_requires=['pytrailer>=0.4',"python-dateutil >= 1.5"],
      classifiers=['Development Status :: 4 - Beta',
                   'License :: OSI Approved :: GNU General Public License (GPL)'
                   'Programming Language :: Python :: 2.6',
                   'Topic :: Software Development :: User Interfaces',
                   'Topic :: Multimedia :: Video'],
      keywords="movie trailer apple module pyqt qt4",
      license="GPLv3",
      platforms=["any"],
      packages=["pyqtrailer",
                "pyqtrailer.qtcustom"],
      package_data={"pyqtrailer.qtcustom":["*.ui"]},
      scripts=["scripts/pyqtrailer"],
      cmdclass={'build_py': build_py},
     )

