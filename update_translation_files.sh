#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Preparing template..."
xgettext --output=po/alpaca.pot --files-from=po/POTFILES
echo "Updating Spanish..."
msgmerge -U po/es.po po/alpaca.pot
echo "Updating Russian..."
msgmerge -U po/ru.po po/alpaca.pot
