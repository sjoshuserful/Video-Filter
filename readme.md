# Josh's GStreamer Color Video Filter
This is code for a GStreamer element "customfilter" that can take in any RGB video and filter out any of the RGB channels.

#### Key:
filter-mode == 0: No change

filter-mode == 1: All red light filtered from video

filter-mode == 2: All green light filtered from video

filter-mode == 3: All blue light filtered from video


### Installation
Josh's Color Video Filter can be easily built and integrated into the GStreamer libraries as it has a custom Meson build environment. Simply complete the following steps:

1. Clone this repository
2. Navigate to the directory in terminal, then navigate to /Video-Filter/build/
3. Run: $ ninja
4. Run: $ sudo ninja install

"customfilter" will now be recognized (provided you use /usr/lib64/gstreamer-1.0/ as your GStreamer libraries directory).
