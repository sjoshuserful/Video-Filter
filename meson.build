project('Video-Filter', 'c')
compiler=meson.get_compiler('c')

include = include_directories('gst')
#'/usr/include/gstreamer-1.0/gst/gst.h', 
#'/usr/include/gstreamer-1.0/gst/video/video.h',
#'/usr/include/gstreamer-1.0/gst/video/gstvideofilter.h',
#'/home/josh/Video-Filter/gstcustomfilter.h'


gstdeps = [
dependency('gstreamer-1.0'),
dependency('gstreamer-base-1.0'),
dependency('gstreamer-video-1.0')
]

executable('customfilter', 'gstcustomfilter.c',include_directories : include, dependencies : gstdeps)
