import os
import sys
import glob
import shutil
import tempfile

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
        tmp_root = os.path.join(tempfile.gettempdir(), "%s" % self.get_basename())
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

    def extract_contents(self):
        # Create a temporary dir to hold the PDF images:
        tmp_dir = tempfile.mkdtemp()
        try:
            # Extract the images:
            tmp_root = os.path.join(tmp_dir, "%s" % self.get_basename())
            execute(["pdfimages", "-j", self.get_filename(), tmp_root])

            # Run a separate instance of the viewer on this dir:
            main_py = os.path.join(os.path.dirname(__file__), "main.py")
            execute([sys.executable, main_py, tmp_dir])
        finally:
            shutil.rmtree(tmp_dir)

    def can_be_extracted(self):
        return True

