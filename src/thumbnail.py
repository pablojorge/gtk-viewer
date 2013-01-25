import gtk

from imagefile import ImageFile, GTKIconImage
from filescanner import FileScanner
from filemanager import FileManager

from cache import Cache, cached

class DirectoryThumbnail(ImageFile):
    cache = Cache(debug=True, top_cache=FileScanner.cache)

    def __init__(self, directory, size=128):
        ImageFile.__init__(self, "")
        self.directory = directory
        self.size = size

    @cached(cache, key_func=lambda self: ("final_thumbnail", self.directory))
    def get_pixbuf(self):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, self.size)

        scanner = FileScanner()
        files = scanner.get_files_from_dir(self.directory)

        if files:
            file_manager = FileManager(on_list_modified=lambda: None)
            file_manager.set_files(files)
            file_manager.sort_by_date(True)
            file_manager.go_first()
            return self.get_mixed_thumbnail(file_manager.get_current_file())
        else:
            return dir_icon.get_pixbuf()

    def get_mixed_thumbnail(self, imagefile):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, self.size)
        ret = dir_icon.get_pixbuf()

        # Magic constants needed to fit the embedded thumbnail inside the 
        # directory icon:
        dir_width = 0.88
        dir_height = 0.54
        dir_offset = 0.62

        width, height = imagefile.get_dimensions_to_fit(self.size * dir_width, 
                                                        self.size * dir_height)
        pixbuf = imagefile.get_pixbuf_at_size(width, height)

        offset_x = int((ret.get_width() - pixbuf.get_width()) / 2)
        offset_y = int((ret.get_height() * dir_offset) - (pixbuf.get_height()/2)) 

        pixbuf.composite(ret, 
                         offset_x, offset_y, 
                         pixbuf.get_width(), pixbuf.get_height(), 
                         offset_x, offset_y, 
                         1, 1, 
                         gtk.gdk.INTERP_HYPER, 
                         255)

        return ret
