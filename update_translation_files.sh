#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Preparing template..."
xgettext --output=po/alpaca.pot --files-from=po/POTFILES
echo "Updating Spanish..."
msgmerge -U po/es.po po/alpaca.pot
#echo "Updating Russian..."
#msgmerge -U po/ru.po po/alpaca.pot
echo "Updating French"
msgmerge -U po/fr.po po/alpaca.pot
echo "Updating Brazilian Portuguese"
msgmerge -U po/pt_BR.po po/alpaca.pot
