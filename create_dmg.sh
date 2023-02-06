#!/bin/bash

# Remove build intermediate from dist/ directory to not include it in the .dmg
# when choosing dist/ as the source folder for create-dmg
# Copying the .app into a dedicated dmg/ directory appears to mess with code
# signing. Don't touch it.
rm -r dist/optoConfig96

readme='Trouble opening? READ ME!.txt'
cat > "dist/${readme}" << EOF
After dragging optoConfig96 into your Applications directory, you may be shown
a popup with one of these messages:

* "optoConfig96" can't be opened because Apple cannot check it for malicious
  software.
* "optoConfig96" cannot be opened because the developer cannot be verified.

In that case, Control-Click on the optoConfig icon and select "Open". You will
be asked if you are sure you want to open it. Once you confirm this,
optoConfig96 will launch.
You can also go to

* "System Preferences > Security & Privacy > General Tab", or
* "System Preferences > Privacy & Security > Security Section",

depending on the version of MacOS you are using, and choose "Open Anyway" for
optoConfig96 after having tried to open it once.

You only need to do this when launching optoConfig96 for the first time.
EOF

# Create a .dmg archive from the .app after building
create-dmg \
    --volname "optoConfig" \
    --volicon "optoConfig96/resources/oc96.icns" \
    --window-size 600 300 \
    --icon-size 100 \
    --icon "optoConfig96.app" 0 120 \
    --icon "${readme}" 300 60 \
    --hide-extension "optoConfig96.app" \
    --hide-extension "${readme}" \
    --app-drop-link 500 120 \
    darwin.dmg dist
