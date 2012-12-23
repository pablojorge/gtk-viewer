import gtk

class ImageViewer:
    def __init__(self):
        self.widget = gtk.Image()
        self.zoom_factor = 100
        self.image_file = None

    def get_widget(self):
        return self.widget

    def get_zoom_factor(self):
        return self.zoom_factor

    def set_zoom_factor(self, zoom_factor):
        if zoom_factor > 1:
            self.zoom_factor = zoom_factor

    def load(self, image_file):
        self.image_file = image_file
        self.set_zoom_factor(100)
        self.redraw()

    def load_at_size(self, image_file, width, height):
        self.image_file = image_file
        self.widget.set_size_request(width, height)
        self.force_zoom(width, height)
        self.redraw()

    def zoom_at_size(self, width, height):
        self.force_zoom(width, height)
        self.redraw()

    def zoom_at(self, zoom_factor):
        self.set_zoom_factor(zoom_factor)
        self.redraw()

    def flip_horizontal(self):
        self.image_file.toggle_flip(True)
        self.redraw()

    def flip_vertical(self):
        self.image_file.toggle_flip(False)
        self.redraw()

    def rotate_c(self):
        self.image_file.rotate(clockwise=True)
        self.redraw()

    def rotate_cc(self):
        self.image_file.rotate(clockwise=False)
        self.redraw()

    def get_scaled_size(self):
        dimensions = self.image_file.get_dimensions()

        width = int((dimensions.get_width() * self.zoom_factor) / 100)
        height = int((dimensions.get_height() * self.zoom_factor) / 100)

        return width, height

    def redraw(self):
        width, height = self.get_scaled_size()
        self.image_file.draw(self.widget, width, height)

    def force_zoom(self, width, height):
        im_dim = self.image_file.get_dimensions()
        zw = (float(width) / im_dim.get_width()) * 99
        zh = (float(height) / im_dim.get_height()) * 99
        self.set_zoom_factor(min(zw, zh))

class ThumbnailViewer(ImageViewer):
    def __init__(self, th_size):
        ImageViewer.__init__(self)
        self.th_size = th_size
        self.hidden = False

    def set_size(self, size):
        self.th_size = size
        self.redraw()

    def load(self, image_file):
        self.load_at_size(image_file, self.th_size, self.th_size)

    def redraw(self):
        if self.hidden:
            return

        if not self.image_file:
            self.fill()
            return

        dimensions = self.image_file.get_dimensions()

        width = int((dimensions.get_width() * self.zoom_factor) / 100)
        height = int((dimensions.get_height() * self.zoom_factor) / 100)

        self.widget.set_from_pixbuf(self.image_file.get_pixbuf_at_size(width, height))

    def fill(self):
        pixbuf = gtk.gdk.Pixbuf(colorspace=gtk.gdk.COLORSPACE_RGB, 
                                has_alpha=False, 
                                bits_per_sample=8, 
                                width=self.th_size, 
                                height=self.th_size)
        pixbuf.fill(0)
        self.widget.set_from_pixbuf(pixbuf)

    def set_tooltip_text(self, text):
        self.widget.set_tooltip_text(text)

    def hide(self):
        self.hidden = True
        self.widget.hide()

    def show(self):
        self.hidden = False
        self.widget.show()
        self.redraw()

    def toggle_visible(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

