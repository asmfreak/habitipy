# register with pypi
register:
	python setup.py register

# prepare pypi distribution package
package:
	python setup.py sdist

# distribute on pypi
distribute:
	python setup.py sdist upload


habitipy/apidoc.txt:
	python3 -c 'from habitipy.api import download_api; print(download_api())' >  $@


mkdocs: docs/* mkdocs.yml
	mkdocs build

test:
	tox
