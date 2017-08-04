all: habitipy/i18n/*/LC_MESSAGES/habitipy.mo
.PRECIOUS: habitipy/i18n/%.po.new
# scrape sources for messages
habitipy/i18n/messages.pot: habitipy/*.py
	xgettext -L python -o $@ $^

# merge changes with previous translations
habitipy/i18n/%.po.new: habitipy/i18n/messages.pot habitipy/i18n/%.po
	$(foreach f,$(filter-out $<,$^),msgmerge $f habitipy/i18n/messages.pot > $(f).new;)

# compile runtime-usable messages
habitipy/i18n/%/LC_MESSAGES/habitipy.mo: habitipy/i18n/%.po.new
	$(foreach f,$^,mkdir -p $(f:.po.new=)/LC_MESSAGES;)
	$(foreach f,$^,msgfmt -o $(f:.po.new=)/LC_MESSAGES/habitipy.mo $(f);)

# fetch new version of docs
habitipy/apidoc.txt:
	python3 -c 'from habitipy.api import download_api; print(download_api())' >  $@

release:
	make tox
	make push
	make bump
	make push
	make pypi
	make clean

tox:
	tox

bump:
	bumpversion patch

push:
	git push
	git push --tags

pypi:
	python setup.py register
	python setup.py sdist upload


mkdocs: docs/* mkdocs.yml
	mkdocs build

clean:
	rm -f habitipy/i18n/*.new habitipy/i18n/messages.pot
