import os
import time
import gtk
import subprocess

import datetime

from imagefile import ImageFile
from cache import Cache, cached
from utils import execute

class VideoFile(ImageFile):
    description = "video"
    valid_extensions = ["avi","mp4","flv","wmv","mpg","mov","m4v"]
    video_cache = Cache(10)

    @cached()
    def get_duration(self):
        output = execute(["ffmpeg", "-i", self.get_filename()], check_retcode=False)
        for line in output.split("\n"):
            tokens = map(lambda s: s.strip(), line.split(","))
            if tokens[0].startswith("Duration:"):
                dummy, duration = tokens[0].split(": ")
                st_time = time.strptime(duration.split(".")[0], "%H:%M:%S")
                delta = datetime.timedelta(hours=st_time.tm_hour,
                                           minutes=st_time.tm_min,
                                           seconds=st_time.tm_sec)
                return delta.seconds

    @cached(video_cache)
    def get_pixbuf(self):
        second_cap = int(round(self.get_duration() * 0.2))
        tmp_dir = "/tmp" # XXX tempfile?
        tmp_root = os.path.join(tmp_dir, "%s" % self.get_basename())
        tmp_img = "%s-000.jpg" % tmp_root
        execute(["ffmpeg", "-ss", str(second_cap), 
                 "-i", self.get_filename(), 
                 "-vframes", "1",
                 "-an",
                 tmp_img])
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(tmp_img)
            os.unlink(tmp_img)
            return pixbuf
        except:
            print "Warning: unable to open", tmp_img
            image = gtk.Image()
            image.set_from_stock("",1)
            return image.get_pixbuf()

    def get_sha1(self):
        # avoiding this for video files
        return "Duration: %s" % datetime.timedelta(seconds=self.get_duration())

    def embedded_open(self, xid):
        popen = subprocess.Popen(["mplayer", self.filename, "-wid", str(xid)],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        return popen.pid

