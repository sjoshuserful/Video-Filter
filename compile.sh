gcc -Wall -Werror -fPIC $CPPFLAGS $(pkg-config --cflags gstreamer-1.0 $pkg) $(pkg-config --cflags gstreamer-base-1.0 $pkg) $(pkg-config --cflags gstreamer-video-1.0 $pkg) -c -o gstcustomfilter.o gstcustomfilter.c

gcc -shared -o gstcustomfilter.so gstcustomfilter.o $(pkg-config --libs gstreamer-1.0 $pkg) $(pkg-config --libs gstreamer-base-1.0 $pkg) $(pkg-config --libs gstreamer-video-1.0 $pkg)

sudo cp gstcustomfilter.so /usr/lib64/gstreamer-1.0/
