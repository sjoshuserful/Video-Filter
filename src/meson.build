gstcustomfilter_sources = [
  'gstcustomfilter.c'
]
gstcustomfilter_deps = [
  glib,
  dep_gst
]

if host_machine.system() == 'linux'
  gstcustomfilter_deps += cc.find_library('dl', required : true)
endif

gstcustomfilter = library('gstcustomfilter', 
  gstcustomfilter_sources,
  dependencies : gstcustomfilter_deps,
  c_args : [
    '-DGST_USE_UNSTABLE_API'
  ],
  include_directories : inc,
  install : true,
  install_dir : 'usr/lib64/gstreamer-1.0'
)
