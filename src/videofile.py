import os
import time
import gtk
import tempfile

import datetime
import pexpect

from imagefile import ImageFile
from cache import Cache, cached
from system import execute
from utils import locked

from threading import Lock

class VideoFile(ImageFile):
    description = "video"
    valid_extensions = ["avi","mp4","flv","wmv","mpg","mov","m4v"]
    video_cache = Cache(10)

    def __init__(self, filename):
        ImageFile.__init__(self, filename)
        self.lock = Lock()

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

    @locked(lambda self: self.lock)
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

    def extract_frames(self, offset, rate, tmp_dir):
        pattern = os.path.join(tmp_dir, "%s-%%06d.jpg" % self.get_basename())

        try:
            child = pexpect.spawn("ffmpeg", ["-ss", str(offset), 
                                             "-i", self.get_filename(), 
                                             "-r", str(rate), 
                                             "-qscale", "1", 
                                             pattern])
            first = True
            while True:
                child.expect("frame=")
                if not first:
                    tokens = filter(lambda x:x, child.before.split(" "))
                    frame = str(tokens[0])
                    yield float(frame) / (self.get_duration() * rate)
                else:
                    first = False
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

    def extract_contents(self, tmp_dir, rate):
        return self.extract_frames(offset=0,
                                   rate=rate,
                                   tmp_dir=tmp_dir)

    def can_be_extracted(self):
        return True

    def get_extract_args(self):
        return [("Frame rate", int, "rate", 1)]

