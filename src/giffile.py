import os
import gtk
import pexpect

from imagefile import ImageFile
from cache import Cache, cached

from system import execute
from threads import yield_processor

class GIFFile(ImageFile):
    description = "gif"
    valid_extensions = ["gif"]
    pixbuf_anim_cache = Cache(10)

    def __init__(self, filename):
        ImageFile.__init__(self, filename)
        self.anim_enabled = False

    def set_anim_enabled(self, enabled):
        self.anim_enabled = enabled

    def draw(self, widget, width, height):
        if self.anim_enabled:
            widget.set_from_animation(self.get_pixbuf_anim_at_size(width, height))
        else:
            widget.set_from_pixbuf(self.get_pixbuf_at_size(width, height))

    @cached(pixbuf_anim_cache)
    def get_pixbuf_anim_at_size(self, width, height):
        loader = gtk.gdk.PixbufLoader()
        loader.set_size(width, height)
        with open(self.get_filename(), "r") as input_:
            buf = input_.read(8192)
            while buf:
                loader.write(buf)
                yield_processor() # Otherwise the UI will lock...
                buf = input_.read(8192)
        loader.close()
        return loader.get_animation()

    def extract_contents(self, tmp_dir):
        try:
            total = len(execute(["identify", self.get_filename()]).split("\n"))

            basename, _, ext = self.get_basename().rpartition(".")
            tmp_root = os.path.join(tmp_dir, "%s_%%04d.%s" % (basename, ext))
            # http://www.imagemagick.org/Usage/anim_basics/#coalesce
            child = pexpect.spawn("convert", ["-verbose",
                                              self.get_filename(), 
                                              "-coalesce", 
                                              tmp_root])

            index = 0
            while True:
                try:
                    child.expect(self.get_filename() + "\=\>")
                    index += 1
                except pexpect.TIMEOUT:
                    pass
                yield float(index) / total

        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

    def can_be_extracted(self):
        return True
