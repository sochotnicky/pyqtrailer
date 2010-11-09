from distutils.command.build_py import build_py as _build_py
from distutils.core import setup
import pyqtrailer
import subprocess
import sys
import os

def get_messages():
    msgfiles = []
    for filename in os.listdir('po/'):
        if filename.endswith('.qm'):
            msgfiles.append('po/%s' % filename)
    return msgfiles

def regen_messages():
    po_files = []
    for filename in os.listdir('po/'):
        if filename.endswith('.po'):
            po_files.append('-i')
            po_files.append(filename)
            po_files.append('-o')
            outFile = filename.replace(".po",'.qm')
            command = ["lconvert", '-i', "po/%s" % filename, '-o', "po/%s" % outFile]
            subprocess.Popen(command)


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
        res = "pyqtrailer/qtcustom/resources.py"

        command = ["pyrcc4", "resources.qrc",
                   "-o", res]
        if sys.version_info[0] == 3:
            command.append('-py3')

        subprocess.Popen(command)
        regen_messages()
        _build_py.run(self)

setup(name='pyqtrailer',
      version=pyqtrailer.__version__,
      description='PyQt4 application to download trailers from www.apple.com/trailers',
      author='Stanislav Ochotnicky',
      author_email='sochotnicky@gmail.com',
      url='http://github.com/sochotnicky/pyqtrailer',
      requires=["pytrailer"],
      install_requires=['pytrailer>=0.5',"python-dateutil >= 1.5"],
      classifiers=['Development Status :: 4 - Beta',
                   'License :: OSI Approved :: GNU General Public License (GPL)',
                   'Programming Language :: Python :: 2.6',
                   'Topic :: Software Development :: User Interfaces',
                   'Topic :: Multimedia :: Video'],
      keywords="movie trailer apple module pyqt qt4",
      license="GPLv3",
      platforms=["any"],
      packages=["pyqtrailer",
                "pyqtrailer.qtcustom"],
      package_data={"pyqtrailer.qtcustom":["*.ui"]},
      data_files = [('/usr/share/pyqtrailer/lang', get_messages())],
      scripts=["scripts/pyqtrailer"],
      cmdclass={'build_py': build_py},
     )

