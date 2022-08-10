/* GStreamer
 * Copyright (C) 2022 FIXME <fixme@example.com>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Suite 500,
 * Boston, MA 02110-1335, USA.
 */
/**
 * SECTION:element-gstcustomfilter
 *
 * The customfilter element does FIXME stuff.
 *
 * <refsect2>
 * <title>Example launch line</title>
 * |[
 * gst-launch-1.0 -v fakesrc ! customfilter ! FIXME ! fakesink
 * ]|
 * FIXME Describe what the pipeline does.
 * </refsect2>
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "gst/gst.h"
#include <gst/video/video.h>
#include <gst/video/gstvideofilter.h>
#include "gstcustomfilter.h"

GST_DEBUG_CATEGORY_STATIC (gst_customfilter_debug_category);
#define GST_CAT_DEFAULT gst_customfilter_debug_category

/* prototypes */


static void gst_customfilter_set_property (GObject * object,
    guint property_id, const GValue * value, GParamSpec * pspec);
static void gst_customfilter_get_property (GObject * object,
    guint property_id, GValue * value, GParamSpec * pspec);
static void gst_customfilter_dispose (GObject * object);
static void gst_customfilter_finalize (GObject * object);

static gboolean gst_customfilter_start (GstBaseTransform * trans);
static gboolean gst_customfilter_stop (GstBaseTransform * trans);
static gboolean gst_customfilter_set_info (GstVideoFilter * filter, GstCaps * incaps,
    GstVideoInfo * in_info, GstCaps * outcaps, GstVideoInfo * out_info);
static GstFlowReturn gst_customfilter_transform_frame (GstVideoFilter * filter,
    GstVideoFrame * inframe, GstVideoFrame * outframe);
static GstFlowReturn gst_customfilter_transform_frame_ip (GstVideoFilter * filter,
    GstVideoFrame * frame);

enum
{
  PROP_0
};

/* pad templates */

/* FIXME: add/remove formats you can handle */
#define VIDEO_SRC_CAPS \
    GST_VIDEO_CAPS_MAKE("{ I420, Y444, Y42B, UYVY, RGBA }")

/* FIXME: add/remove formats you can handle */
#define VIDEO_SINK_CAPS \
    GST_VIDEO_CAPS_MAKE("{ I420, Y444, Y42B, UYVY, RGBA }")


/* class initialization */

G_DEFINE_TYPE_WITH_CODE (GstCustomfilter, gst_customfilter, GST_TYPE_VIDEO_FILTER,
  GST_DEBUG_CATEGORY_INIT (gst_customfilter_debug_category, "customfilter", 0,
  "debug category for customfilter element"));

static void
gst_customfilter_class_init (GstCustomfilterClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);
  GstBaseTransformClass *base_transform_class = GST_BASE_TRANSFORM_CLASS (klass);
  GstVideoFilterClass *video_filter_class = GST_VIDEO_FILTER_CLASS (klass);

  /* Setting up pads and setting metadata should be moved to
     base_class_init if you intend to subclass this class. */
  gst_element_class_add_pad_template (GST_ELEMENT_CLASS(klass),
      gst_pad_template_new ("src", GST_PAD_SRC, GST_PAD_ALWAYS,
        gst_caps_from_string (VIDEO_SRC_CAPS)));
  gst_element_class_add_pad_template (GST_ELEMENT_CLASS(klass),
      gst_pad_template_new ("sink", GST_PAD_SINK, GST_PAD_ALWAYS,
        gst_caps_from_string (VIDEO_SINK_CAPS)));

  gst_element_class_set_static_metadata (GST_ELEMENT_CLASS(klass),
      "FIXME Long name", "Generic", "FIXME Description",
      "FIXME <fixme@example.com>");

  gobject_class->set_property = gst_customfilter_set_property;
  gobject_class->get_property = gst_customfilter_get_property;
  gobject_class->dispose = gst_customfilter_dispose;
  gobject_class->finalize = gst_customfilter_finalize;
  base_transform_class->start = GST_DEBUG_FUNCPTR (gst_customfilter_start);
  base_transform_class->stop = GST_DEBUG_FUNCPTR (gst_customfilter_stop);
  video_filter_class->set_info = GST_DEBUG_FUNCPTR (gst_customfilter_set_info);
  video_filter_class->transform_frame = GST_DEBUG_FUNCPTR (gst_customfilter_transform_frame);
  video_filter_class->transform_frame_ip = GST_DEBUG_FUNCPTR (gst_customfilter_transform_frame_ip);

}

static void
gst_customfilter_init (GstCustomfilter *customfilter)
{
}

void
gst_customfilter_set_property (GObject * object, guint property_id,
    const GValue * value, GParamSpec * pspec)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (object);

  GST_DEBUG_OBJECT (customfilter, "set_property");

  switch (property_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
  }
}

void
gst_customfilter_get_property (GObject * object, guint property_id,
    GValue * value, GParamSpec * pspec)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (object);

  GST_DEBUG_OBJECT (customfilter, "get_property");

  switch (property_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      break;
  }
}

void
gst_customfilter_dispose (GObject * object)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (object);

  GST_DEBUG_OBJECT (customfilter, "dispose");

  /* clean up as possible.  may be called multiple times */

  G_OBJECT_CLASS (gst_customfilter_parent_class)->dispose (object);
}

void
gst_customfilter_finalize (GObject * object)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (object);

  GST_DEBUG_OBJECT (customfilter, "finalize");

  /* clean up object here */

  G_OBJECT_CLASS (gst_customfilter_parent_class)->finalize (object);
}

static gboolean
gst_customfilter_start (GstBaseTransform * trans)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (trans);

  GST_DEBUG_OBJECT (customfilter, "start");

  return TRUE;
}

static gboolean
gst_customfilter_stop (GstBaseTransform * trans)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (trans);

  GST_DEBUG_OBJECT (customfilter, "stop");

  return TRUE;
}

static gboolean
gst_customfilter_set_info (GstVideoFilter * filter, GstCaps * incaps,
    GstVideoInfo * in_info, GstCaps * outcaps, GstVideoInfo * out_info)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (filter);

  GST_DEBUG_OBJECT (customfilter, "set_info");

  return TRUE;
}

/* transform */
static GstFlowReturn
gst_customfilter_transform_frame (GstVideoFilter * filter, GstVideoFrame * inframe,
    GstVideoFrame * outframe)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (filter);

  GST_DEBUG_OBJECT (customfilter, "transform_frame");

  return GST_FLOW_OK;
}

static GstFlowReturn
gst_customfilter_transform_frame_ip (GstVideoFilter * filter, GstVideoFrame * frame)
{
  GstCustomfilter *customfilter = GST_CUSTOMFILTER (filter);

  GST_DEBUG_OBJECT (customfilter, "transform_frame_ip");

  return GST_FLOW_OK;
}

static gboolean
plugin_init (GstPlugin * plugin)
{

  /* FIXME Remember to set the rank if it's an element that is meant
     to be autoplugged by decodebin. */
  return gst_element_register (plugin, "customfilter", GST_RANK_NONE,
      GST_TYPE_CUSTOMFILTER);
}

/* FIXME: these are normally defined by the GStreamer build system.
   If you are creating an element to be included in gst-plugins-*,
   remove these, as they're always defined.  Otherwise, edit as
   appropriate for your external plugin package. */
#ifndef VERSION
#define VERSION "0.0.FIXME"
#endif
#ifndef PACKAGE
#define PACKAGE "FIXME_package"
#endif
#ifndef PACKAGE_NAME
#define PACKAGE_NAME "FIXME_package_name"
#endif
#ifndef GST_PACKAGE_ORIGIN
#define GST_PACKAGE_ORIGIN "http://FIXME.org/"
#endif

GST_PLUGIN_DEFINE (GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    customfilter,
    "FIXME plugin description",
    plugin_init, VERSION, "LGPL", PACKAGE_NAME, GST_PACKAGE_ORIGIN)

