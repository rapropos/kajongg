#!/bin/sh
# http://www.gnu.org/software/autoconf/manual/gettext/xgettext-Invocation.html
# http://api.kde.org/4.0-api/kdelibs-apidocs/kdecore/html/classKLocalizedString.html
# extract messages from *.py

# currently, the .pot lives at
# http://websvn.kde.org/trunk/l10n-kf5/templates/messages/kdegames/kajongg.pot

${EXTRACTRC:-extractrc} src/*.ui src/*.rc >> rc.cpp

${XGETTEXT:-xgettext} \
		-ci18n --from-code=UTF-8 --language=Python -k \
		-ki18n:1 -ki18nc:1c,2 -ki18np:1,2 \
                -ki18nE:1 -ki18ncE:1c,2 \
		-ki18ncp:1c,2,3 -ktr2i18n:1 \
		-kI18N_NOOP:1 -kI18N_NOOP2:1c,2 \
		-kaliasLocale \
		-kcreateRule:1 \
		--no-wrap --msgid-bugs-address=wolfgang@rohdewald.de -o${podir:-.}/kajongg.pot \
		rc.cpp `find . -name \*.py`
