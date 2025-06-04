#!/bin/bash
# create python files from Qt5 Designer
for fname in designer/*.ui; do
  name=${fname%.*}
  name=${name#designer/*}
  if [ "designer/$name.ui" -nt "gpedit/$name.py" ] || [ ! -f "gpedit/$name.py" ]; then 
    echo "$name.ui"
    pyuic5 --from-imports -i 2 "designer/$name.ui" -o "gpedit/$name.py"
  fi
done
if [ "designer/icons.qrc" -nt "gpedit/icons_rc.py" ] || [ ! -f "gpedit/icons_rc.py" ]; then 
  echo "icons.qrc"
  pyrcc5 designer/icons.qrc -o gpedit/icons_rc.py
fi
