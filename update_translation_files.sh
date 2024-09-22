#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Preparing template..."
xgettext --output=po/alpaca.pot --files-from=po/POTFILES
echo "Updating Spanish..."
msgmerge --no-fuzzy-matching -U po/es.po po/alpaca.pot
echo "Updating Russian..."
msgmerge --no-fuzzy-matching -U po/ru.po po/alpaca.pot
echo "Updating French"
msgmerge --no-fuzzy-matching -U po/fr.po po/alpaca.pot
echo "Updating Brazilian Portuguese"
msgmerge --no-fuzzy-matching -U po/pt_BR.po po/alpaca.pot
echo "Updating Norwegian"
msgmerge --no-fuzzy-matching -U po/nb_NO.po po/alpaca.pot
echo "Updating Bengali"
msgmerge --no-fuzzy-matching -U po/bn.po po/alpaca.pot
echo "Updating Simplified Chinese"
msgmerge --no-fuzzy-matching -U po/zh_Hans.po po/alpaca.pot
echo "Updating Hindi"
msgmerge --no-fuzzy-matching -U po/hi.po po/alpaca.pot
echo "Updating Turkish"
msgmerge --no-fuzzy-matching -U po/tr.po po/alpaca.pot
echo "Updating Ukrainian"
msgmerge --no-fuzzy-matching -U po/uk.po po/alpaca.pot
echo "Updating German"
msgmerge --no-fuzzy-matching -U po/de.po po/alpaca.pot
echo "Updating Hebrew"
msgmerge --no-fuzzy-matching -U po/he.po po/alpaca.pot
echo "Updating Telugu"
msgmerge --no-fuzzy-matching -U po/te.po po/alpaca.pot