# Contributing

Clone, contribute, create a pull request, and nudge philadams to review it. Do remember to add yourself to `CONTRIBUTORS.md`.

Work gets a bit crazy at times, so there might be a short wait, but I'll get to
your PR as soon as possible! Thank you for your interest in the project and for
contributing your time.

# Releases

Remember to update the [Habitica command line
tool](http://habitica.wikia.com/wiki/Habitica_Command_Line_Tool) page on the
Habitica wikia with the latest release number and date.

## Internalization (I18N)
Habitipy use Python's builtin `gettext` module to translate messages. If you want to create a new translation for your language, please follow the following instruction.
Messages for translation are scraped from code using `xgettext` utility. It generates a template file with extension `pot`, which is then used to generate and update actual translation file with extansion `po`. This is done using `msginit` and `msgmerge` cli utilities to generate and update translation files respectively.
Translation files are kept under `habitipy/i18n` folder with two-letter language code they have translation for.

Any language have a two-letter code. If unsure what code corresponds to your language, please read [this wikipedia article](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes). **From here onward any use of word `yourlang` MUST be replaced with your language's two-letter code.** So a file containing translation for your language will be named `habitipy/i18n/yourlang.po`. For example, russian translation file will be named `habitipy/i18n/ru.po`

When application is running it will use a binary translation file `habitipy/i18n/yourlang/LC_MESSAGES/habitipy.mo`. Those files are generated from `habitipy/i18n/yourlang.po` which contain the actual translation. The encoding of `mo` files from `po` files is done using `msgfmt` cli utility.

Except for initial `po` file generation other operations should run automatically by using `make`.

### Create a new translation

Run these commands to get yourself a new translation file:
```
make
msginit -i habitipy/i18n/messages.pot -o habitipy/i18n/yourlang.po
```
Then edit `habitica_planner/i18n/yourlang.po` with translations.
