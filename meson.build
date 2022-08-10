project('gst-customfilter', 'c',
  version : '0.0.1',
  license : ['LGPL'],
  meson_version : '>= 0.52.0',
  default_options : [
    'warning_level=2',
    'buildtype=debug',
    'c_std=gnu99'
  ]
)

cc = meson.get_compiler('c')

gst_api_version = '1.0'
glib = dependency('glib-2.0')
dep_gst  = \
    [ dependency('gstreamer-1.0',              include_type: 'system')
    , dependency('gstreamer-app-1.0',          include_type: 'system')
    , dependency('gstreamer-base-1.0',         include_type: 'system')
    , dependency('gstreamer-pbutils-1.0',      include_type: 'system')
    , dependency('gstreamer-plugins-base-1.0', include_type: 'system')
    , dependency('gstreamer-rtsp-1.0',         include_type: 'system')
    , dependency('gstreamer-rtsp-server-1.0',  include_type: 'system')
    , dependency('gstreamer-video-1.0',        include_type: 'system')
    ]

#data_install_dir = get_option('datadir') / meson.project_name()

inc = include_directories('.')

subdir('src')
