import os
import glob

import gtk

from imagefile import ImageFile
from cache import Cache, cached
from system import execute

class PDFFile(ImageFile):
    description = "pdf"
    valid_extensions = ["pdf"]
    pixbuf_cache = Cache(10)

    @cached(pixbuf_cache)
    def get_pixbuf(self):
        tmp_dir = "/tmp" # XXX tempfile?
        tmp_root = os.path.join(tmp_dir, "%s" % self.get_basename())
        execute(["pdfimages", "-f", "1", "-l", "1", "-j", 
                 self.get_filename(), 
                 tmp_root])

        for ext in ["jpg", "pbm", "ppm"]:
            try:
                tmp_img = "%s-000.%s" % (tmp_root, ext)
                pixbuf = gtk.gdk.pixbuf_new_from_file(tmp_img)
                for filename in glob.glob(tmp_root + "*"):
                    os.unlink(filename)
                return pixbuf
            except:
                continue

        print "Warning: unable to preview PDF file '%s'" % self.get_basename()
        return self.get_empty_pixbuf()

