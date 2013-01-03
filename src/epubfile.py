import os
import re
import zipfile
from xml.dom import minidom

import gtk
import gio

from imagefile import ImageFile
from cache import Cache, cached

class EPUBFile(ImageFile):
    description = "epub"
    valid_extensions = ["epub"]
    pixbuf_cache = Cache(10)

    @cached(pixbuf_cache)
    def get_pixbuf(self):
        cover = self.get_cover()

        if cover:
            stream = gio.memory_input_stream_new_from_data(cover.read())
            return gtk.gdk.pixbuf_new_from_stream(stream)
        else:
            print "Warning: unable to preview EPUB file '%s'" % self.get_basename()
            return self.get_empty_pixbuf()

    def get_cover(self):
        epub = zipfile.ZipFile(self.filename, "r")

        for strategy in [self.get_cover_from_manifest,
                         self.get_cover_by_filename]:
            # Try to obtain the cover with the current method:
            cover_path = strategy(epub)

            # If succesfull, extract the cover and build the pixbuf:
            if cover_path:
                return epub.open(cover_path)
        
        return None

    def get_cover_from_manifest(self, epub):
        img_ext_regex = re.compile("^.*\.(jpg|jpeg|png)$")

        # open the main container
        container = epub.open("META-INF/container.xml")
        container_root = minidom.parseString(container.read())

        # locate the rootfile
        elem = container_root.getElementsByTagName("rootfile")[0]
        rootfile_path = elem.getAttribute("full-path")

        # open the rootfile
        rootfile = epub.open(rootfile_path)
        rootfile_root = minidom.parseString(rootfile.read())

        # find the manifest element
        manifest = rootfile_root.getElementsByTagName("manifest")[0]
        for item in manifest.getElementsByTagName("item"):
            item_id = item.getAttribute("id")
            item_href = item.getAttribute("href")
            if (("cover" in item_id or "fcvi" in item_id) and 
                img_ext_regex.match(item_href.lower())):
                cover_path = os.path.join(os.path.dirname(rootfile_path), 
                                          item_href)
                return cover_path

        return None

    def get_cover_by_filename(self, epub):
        cover_regex = re.compile(".*cover.*\.(jpg|jpeg|png)")

        for fileinfo in epub.filelist:
            if cover_regex.match(os.path.basename(fileinfo.filename).lower()):
                return fileinfo.filename

        return None

