.PHONY: all mypy flake8 tests

#------------------------------------------------------------------------------
# Tests, validation, mypy.
#------------------------------------------------------------------------------

all: mypy flake8 tests

mypy:
	mypy --strict src tests

tests:
	python3 -m unittest

# W503 and W504 are both enabled by default and are mutual
# contradictory, so we have to suppress one of them.
# E501 uses 79 columns by default, but 80 is the default line wrap in
# vim, so change the line-length.
flake8:
	flake8 . \
		--exclude=archive,zonedbpy \
		--count \
		--ignore W503 \
		--show-source \
		--statistics \
		--max-line-length=80

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

# Generate the validation_data.json for testing purposes
validation_data.json: zones.txt
	./compare_pytz/generate_data.py < $< > $@

# Generate the validation_data.{h,cpp}, validation_tests.cpp
validation_data.h: validation_data.json
	./generate_validation.py \
		--tz_version $(TZ_VERSION) \
		--scope basic \
		--db_namespace zonedb \
		< $<

validation_data.cpp: validation_data.h
	@true

validation_tests.cpp: validation_data.h
	@true

#------------------------------------------------------------------------------
# Rules to compile various compare_xxx validation data generators.
#------------------------------------------------------------------------------

compares:
	$(MAKE) -C compare_acetz
	$(MAKE) -C compare_cpp
	$(MAKE) -C compare_dateutil
	$(MAKE) -C compare_java
	$(MAKE) -C compare_pytz
	# TODO: Add C# compilation test
	# $(MAKE) -C compare_noda

#------------------------------------------------------------------------------

clean:
	rm -f zones.txt zonedb.json zonedbx.json validation_data.json \
		validation_data.h validation_data.cpp validation_tests.cpp
	rm -rf $(TZ_VERSION)
	$(MAKE) -C compare_pytz clean
	$(MAKE) -C compare_dateutil clean
	$(MAKE) -C compare_java clean
	$(MAKE) -C compare_cpp clean
	$(MAKE) -C compare_noda clean
