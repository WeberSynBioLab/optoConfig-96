DOCS=docs
DOCS_IMAGES_RAW=$(DOCS)/images
DOCS_IMAGES_ANNOTATED=$(DOCS_IMAGES_RAW)/annotated
ANNOTATED_TIKZ=$(wildcard $(DOCS_IMAGES_ANNOTATED)/*.tikz)
ANNOTATED_JPGS=$(patsubst %.tikz, %.jpg, $(ANNOTATED_TIKZ))
PKG_DOCS=optoConfig96/resources/docs

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
	tail -n+5 docs/guide.md > README.md
	# Make image paths relative to root
	sed -i "s|images/|docs/images/|g" README.md

generate_package: generate_docs
	# Copy docs to resources folder to make the documentation available from
	# within the application
	rm -rf $(PKG_DOCS)
	mkdir -p $(PKG_DOCS)/images/annotated
	cp $(DOCS)/*.{css,html} $(PKG_DOCS)
	cp $(DOCS)/images/*.jpg $(PKG_DOCS)/images
	cp $(DOCS)/images/annotated/*.jpg $(PKG_DOCS)/images/annotated
	python -m build

.PHONY: test_install
test_install:
	rm -rf test_install
	mkdir test_install ; cd test_install ; \
		python -m venv test_install_venv ; \
		source test_install_venv/bin/activate ; \
		pip install ../dist/optoConfig96-1.0.3.tar.gz ; \
		python -m optoConfig96
