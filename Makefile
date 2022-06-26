DOCS := docs
DOCS_IMAGES_RAW := $(DOCS)/images
DOCS_IMAGES_ANNOTATED := $(DOCS_IMAGES_RAW)/annotated
ANNOTATED_TIKZ := $(wildcard $(DOCS_IMAGES_ANNOTATED)/*.tikz)
ANNOTATED_JPGS := $(patsubst %.tikz, %.jpg, $(ANNOTATED_TIKZ))
PKG_DOCS := optoConfig96/resources/docs

VERSION := $(shell grep -oE '[0-9]+[.][0-9]+[.][0-9]+' optoConfig96/version.py)

all: generate_package

generate_docs: $(ANNOTATED_JPGS) $(DOCS)/optoConfig96_guide.html README.md

$(DOCS_IMAGES_ANNOTATED)/%.jpg: $(DOCS_IMAGES_ANNOTATED)/%.tikz
	cd $(DOCS_IMAGES_ANNOTATED) ; \
		pdflatex  $(notdir $<)
	gs -sDEVICE=png16m -dJPEGQ=90 -dTextAlphaBits=4 -dGraphicsAlphaBits=4 \
		-dDOINTERPOLATE -r95 -o $@ $(patsubst %.tikz, %.pdf, $<)
	rm $(DOCS_IMAGES_ANNOTATED)/*.{aux,log,pdf}

$(DOCS)/optoConfig96_guide.html: $(DOCS)/guide.md
	pandoc -s $< --css guide.css -o $@

README.md: $(DOCS)/guide.md
	# Ignore YAML header
	tail -n+5 docs/guide.md > "$@"
	# Make image paths relative to root
	sed -i "s|images/|docs/images/|g" "$@"

check_version_numbers: README.md docs/guide.md
	for f in $<; do \
		if [ $$(grep -oE '[0-9]+[.][0-9]+[.][0-9]+' $$f) != "$(VERSION)" ]; then \
			echo "Fix version number in $$f!" >&2 ; \
			exit 1 ; \
		fi ; \
	done

generate_package: generate_docs check_version_numbers
	# Copy docs to resources folder to make the documentation available from
	# within the application
	rm -rf $(PKG_DOCS)
	mkdir -p $(PKG_DOCS)/images/annotated
	cp $(DOCS)/*.css $(PKG_DOCS)
	cp $(DOCS)/*.html $(PKG_DOCS)
	cp $(DOCS)/images/*.jpg $(PKG_DOCS)/images
	cp $(DOCS)/images/annotated/*.jpg $(PKG_DOCS)/images/annotated
	python3 -m build

.PHONY: test_install
test_install: generate_package
	rm -rf test_install
	mkdir test_install ; cd test_install ; \
		python3 -m venv test_install_venv ; \
		. test_install_venv/bin/activate ; \
		python3 -m pip install ../dist/optoConfig96-$(VERSION).tar.gz ; \
		python3 -m optoConfig96
