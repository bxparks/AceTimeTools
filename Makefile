.PHONY: all mypy flake8 tests

#------------------------------------------------------------------------------
# Tests, validation, mypy.
#------------------------------------------------------------------------------

all: mypy flake8 tests

# The '../AceTimePython/src/acetime' is added because MyPy complains about not
# finding the typing info when AceTimePython is installed using 'pip3 install'.
# Seems like typing info is not being installed by pip3.
mypy:
	mypy --strict src tests ../AceTimePython/src/acetime

tests:
	python3 -m unittest

# W503 and W504 are both enabled by default and are mutual
# contradictory, so we have to suppress one of them.
# E501 uses 79 columns by default, but 80 is the default line wrap in
# vim, so change the line-length.
flake8:
	flake8 . \
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
# not affect the zonedb files generated in AceTime or AceTimePython.
TZ_VERSION := 2021a

# Copy the TZ DB files into this directory for testing purposes.
$(TZ_VERSION):
	./copytz.sh $(TZ_VERSION)

# Run the Validator using validate.py.
validate: $(TZ_VERSION)
	./src/acetimetools/validate.py \
		--input_dir $(TZ_VERSION) \
		--scope extended

# Generate zonedb.json for testing purposes.
zonedb.json: $(TZ_VERSION)
	./src/acetimetools/tzcompiler.py \
		--tz_version $(TZ_VERSION) \
		--input_dir $(TZ_VERSION) \
		--scope basic \
		--language json \
		--json_file $@ \
		--start_year 2000 \
		--until_year 2050

# Generate zonedbx.json for testing purposes.
zonedbx.json: $(TZ_VERSION)
	./src/acetimetools/tzcompiler.py \
		--tz_version $(TZ_VERSION) \
		--input_dir $(TZ_VERSION) \
		--scope extended \
		--language json \
		--json_file $@ \
		--start_year 2000 \
		--until_year 2050

# Generate the zones.txt file for testing purposes.
zones.txt: $(TZ_VERSION)
	./src/acetimetools/tzcompiler.py \
		--tz_version $(TZ_VERSION) \
		--input_dir $(TZ_VERSION) \
		--scope basic \
		--language zonelist

#------------------------------------------------------------------------------

clean:
	rm -f zones.txt zonedb.json zonedbx.json validation_data.json \
		validation_data.h validation_data.cpp validation_tests.cpp
	rm -rf $(TZ_VERSION)
