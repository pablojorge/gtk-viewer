import os
import glob
import string
import tempfile
import pexpect

import gtk

from imagefile import ImageFile, GTKIconImage
from cache import Cache, cached
from system import execute

class PDFFile(ImageFile):
    description = "pdf"
    valid_extensions = ["pdf"]
    pixbuf_cache = Cache(10)

    @cached()
    def get_metadata(self):
        info = [("Property", "Value")]
        output = execute(["pdfinfo", self.get_filename()], check_retcode=False)
        for line in filter(lambda x: x, output.split("\n")):
            tokens = map(string.strip, line.split(":"))
            info.append((tokens[0], string.join(tokens[1:], "")))
        return info

    @cached()
    def get_pages(self):
        try: 
            return int(dict(self.get_metadata()).get("Pages", "0"))
        except KeyError:
            return 0

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
        return GTKIconImage(gtk.STOCK_MISSING_IMAGE, 256).get_pixbuf()

    def get_sha1(self):
        # avoiding this for PDF files
        return "Pages: %d" % (self.get_pages())

    def extract_contents(self, tmp_dir):
        try:
            tmp_root = os.path.join(tmp_dir, "%s" % self.get_basename())
            child = pexpect.spawn("pdfimages", ["-j", self.get_filename(), tmp_root])
            while True:
                try:
                    child.expect("", 0)
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

    def can_be_extracted(self):
        return True

class PDFGenerator:
    def generate(self, files, output):
        try:
            child = pexpect.spawn("convert", ["-verbose"] +
                                              files + 
                                              [output])
            while True:
                try:
                    child.expect("\=\>" + output, 0.2)
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

    def get_args(self):
        return []
