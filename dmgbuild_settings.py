# """ Settings for creating a Mac disk image from the app. """

# dmgbuild doesn't run from the proper directory: injected via build.py


file_name = f'{appname}-{version}.dmg'
volume_name = f'{appname}-{version}'
files = [raw_target]
default_view = 'icon-view'
symlinks = {'Applications': '/Applications'}
icon_locations = {
    appname: (140, 120),
    'Applications': (500, 120)
}
background = 'builtin-arrow'

icon = mac_icon_path
