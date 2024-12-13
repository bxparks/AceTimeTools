.PHONY: all mypy flake8 tests zonedb.json zonedbx.json

#------------------------------------------------------------------------------
# Tests, validation, mypy.
#------------------------------------------------------------------------------

all: mypy flake8 tests

# The '../acetimepy/src/acetime' is added because MyPy complains about not
# finding the typing info when acetimepy is installed using 'pip3 install'.
# Seems like typing info is not being installed by pip3.
mypy:
	python3 -m mypy --strict src tests ../acetimepy/src/acetime

tests:
	python3 -m unittest

# W503 and W504 are both enabled by default and are mutual
# contradictory, so we have to suppress one of them.
# E501 uses 79 columns by default, but 80 is the default line wrap in
# vim, so change the line-length.
flake8:
	python3 -m flake8 . \
		--exclude=archive \
		--ignore W503 \
		--max-line-length=80 \
		--show-source \
		--statistics \
		--count

#------------------------------------------------------------------------------
# Rules for manual testing.
#------------------------------------------------------------------------------

# The TZ DB version used for internal testing targets defined below. This does
# not affect the zonedb files generated in AceTime or acetimepy.
TZ_VERSION := 2024b
TZ_REPO := $(abspath ../tz)

# Generate zonedb.json for testing purposes.
zonedb.json:
	./tzcompiler.sh \
		--tzrepo $(TZ_REPO) \
		--tag $(TZ_VERSION) \
		--action json \
		--languages arduino \
		--scope basic \
		--json_file $@ \
		--start_year 1980 \
		--until_year 2100

# Generate zonedbx.json for testing purposes.
zonedbx.json:
	./tzcompiler.sh \
		--tzrepo $(TZ_REPO) \
		--tag $(TZ_VERSION) \
		--action json \
		--languages arduino \
		--scope extended \
		--json_file $@ \
		--start_year 1974 \
		--until_year 2100

# Generate zonedbc.json for testing purposes.
zonedbc.json:
	./tzcompiler.sh \
		--tzrepo $(TZ_REPO) \
		--tag $(TZ_VERSION) \
		--action json \
		--languages arduino \
		--scope complete \
		--json_file $@ \
		--start_year 1800 \
		--until_year 2200

# Generate the zones.txt file for testing purposes.
zones.txt:
	./tzcompiler.sh \
		--tzrepo $(TZ_REPO) \
		--tag $(TZ_VERSION) \
		--scope basic \
		--action zonelist \
		--languages arduino

#------------------------------------------------------------------------------

clean:
	rm -f zonedb.json zonedbx.json zonedbc.json zones.txt
