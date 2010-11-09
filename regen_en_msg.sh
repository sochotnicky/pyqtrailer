#!/bin/sh
pylupdate4 `find pyqtrailer/ -name '*.py'` -ts temp.ts

lconvert --source-language en_GB -i temp.ts --target-language en_GB -o po/messages.po
