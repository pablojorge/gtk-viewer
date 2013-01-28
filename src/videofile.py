import os
import time
import gtk
import tempfile

import datetime

from imagefile import ImageFile
from cache import Cache, cached
from system import execute

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

        return 0

    @cached(video_cache)
    def get_pixbuf(self):
        second_cap = int(round(self.get_duration() * 0.2))
        tmp_root = os.path.join(tempfile.gettempdir(), "%s" % self.get_basename())
        tmp_img = "%s-000.jpg" % tmp_root

        try:
            self.extract_frame_at(second_cap, tmp_img)
        except:
            print "Warning: unable to extract thumbnail from '%s'" % self.get_basename()
            return self.get_empty_pixbuf()

        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(tmp_img)
            os.unlink(tmp_img)
            return pixbuf
        except:
            print "Warning: unable to open", tmp_img
            return self.get_empty_pixbuf()

    def extract_frame_at(self, second, output):
        execute(["ffmpeg", "-ss", str(second), 
                 "-i", self.get_filename(), 
                 "-vframes", "1",
                 "-an",
                 output])

    def get_sha1(self):
        # avoiding this for video files
        return "Duration: %s (%d seconds)" % (datetime.timedelta(seconds=self.get_duration()),
                                              self.get_duration())

    def extract_contents(self, tmp_dir):
        try:
            tmp_root = os.path.join(tmp_dir, "%s" % self.get_basename())
            for second in range(self.get_duration()):
                tmp_img = "%s-%06d.jpg" % (tmp_root, second)
                self.extract_frame_at(second, tmp_img)
                yield float(second) / self.get_duration()
        except:
            pass

    def can_be_extracted(self):
        return True

