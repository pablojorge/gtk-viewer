import gtk

from imagefile import ImageFile
from cache import Cache, cached

class GIFFile(ImageFile):
    description = "gif"
    valid_extensions = ["gif"]
    pixbuf_anim_cache = Cache(10)
    anim_toggle = False

    def embedded_open(self, xid):
        GIFFile.anim_toggle = not GIFFile.anim_toggle

    def draw(self, widget, width, height):
        if GIFFile.anim_toggle:
            widget.set_from_animation(self.get_pixbuf_anim_at_size(width, height))
        else:
            widget.set_from_pixbuf(self.get_pixbuf_at_size(width, height))

    @cached(pixbuf_anim_cache)
    def get_pixbuf_anim_at_size(self, width, height):
        loader = gtk.gdk.PixbufLoader()
        loader.set_size(width, height)
        with open(self.get_filename(), "r") as input_:
            loader.write(input_.read())
        loader.close()
        return loader.get_animation()

