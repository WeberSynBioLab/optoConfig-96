PKG_RESOURCES := optoConfig96/resources
PKG_DOCS := $(PKG_RESOURCES)/docs
DOCS_IMAGES_RAW := $(PKG_DOCS)/images
DOCS_IMAGES_ANNOTATED := $(DOCS_IMAGES_RAW)/annotated
ANNOTATED_TIKZ := $(wildcard $(DOCS_IMAGES_ANNOTATED)/*.tikz)
ANNOTATED_JPGS := $(patsubst %.tikz, %.jpg, $(ANNOTATED_TIKZ))

VERSION := $(shell grep -oE '[0-9]+[.][0-9]+[.][0-9]+' optoConfig96/version.py)


$(PKG_DOCS)/optoConfig96_guide.html: $(PKG_DOCS)/guide.md $(ANNOTATED_JPGS) check_version_number
	pandoc -s $< --css guide.css -o $@


$(DOCS_IMAGES_ANNOTATED)/%.jpg: $(DOCS_IMAGES_ANNOTATED)/%.tikz
	cd $(DOCS_IMAGES_ANNOTATED) ; \
		pdflatex  $(notdir $<)
	gs -sDEVICE=png16m -dJPEGQ=90 -dTextAlphaBits=4 -dGraphicsAlphaBits=4 \
		-dDOINTERPOLATE -r95 -o $@ $(patsubst %.tikz, %.pdf, $<)
	rm $(DOCS_IMAGES_ANNOTATED)/*.{aux,log,pdf}


README.md: $(PKG_DOCS)/guide.md
	# Ignore YAML header
	tail -n+5 "$<" > "$@"
	# Make image paths relative to root
	sed -i "s|images/|$(PKG_DOCS)/images/|g" "$@"


$(PKG_RESOURCES)/oc96.icns: $(PKG_RESOURCES)/oc96.iconset
	# Create MacOS iconset
	iconutil -c icns --output "$@" "$<"

check_version_number: $(PKG_DOCS)/guide.md README.md optoConfig96/version.py
	# Check if version number in guide matches program version
	for f in $<; do \
		if [ $$(grep -oE '[0-9]+[.][0-9]+[.][0-9]+' $$f) != "$(VERSION)" ]; then \
			echo "Fix version number in $$f!" >&2 ; \
			exit 1 ; \
		fi ; \
	done
