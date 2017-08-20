all: habitipy/i18n/*/LC_MESSAGES/habitipy.mo
.PRECIOUS: habitipy/i18n/%.po.new
# scrape sources for messages
habitipy/i18n/messages.pot: habitipy/*.py
	xgettext --from-code utf-8  -L python -o $@ $^

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
	make tag
	make push
	make pypi
	make clean

tox:
	tox

bump:
	bumpversion patch

tag:
	$(eval VERSION:=v$(shell bumpversion --dry-run --list patch | grep curr | sed -e 's/^.*=//g'))
	$(eval PREV_TAG:=$(shell git describe --tags --abbrev=0))
	(printf "Changes made in this version: \n"; git log $(PREV_TAG)..HEAD --graph --oneline --pretty="%h - %s") | git tag -F - -s $(VERSION)

push:
	git push
	git push --tags

pypi:
	python3 setup.py sdist upload --sign
#	python3 setup.py bdist_wheel upload --sign

pydocmdinit: SHELL:=/bin/bash
pydocmdinit:
	(\
		python3 -m venv .pydocenv &&\
		source .pydocenv/bin/activate &&\
		pip install pydoc-markdown mkdocs-material fontawesome_markdown&&\
		pip install -e . \
	)

docs_build: SHELL:=/bin/bash
docs_build: docs/* pydocmd.yml
	(\
		source .pydocenv/bin/activate && \
		pydocmd build\
	)

docs_deploy: SHELL:=/bin/bash
docs_deploy: docs/* pydocmd.yml
	(\
		source .pydocenv/bin/activate && \
		pydocmd gh-deploy\
	)

clean_translation:
	rm -f habitipy/i18n/*.new habitipy/i18n/messages.pot

clean_docs:
	rm -rf .pydocenv
