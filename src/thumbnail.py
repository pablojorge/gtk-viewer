import gtk

from imagefile import ImageFile, GTKIconImage
from filescanner import FileScanner
from filemanager import FileManager

from cache import Cache, cached

class DirectoryThumbnail(ImageFile):
    cache = Cache(top_cache=FileScanner.cache)
    default_thumbnail_size = 512
    default_gtk_icon_size = 128

    def __init__(self, directory):
        ImageFile.__init__(self, "")
        self.directory = directory

    @cached(cache, key_func=lambda self: ("pixbuf", self.directory))
    def get_pixbuf(self):
        scanner = FileScanner()
        files = scanner.get_files_from_dir(self.directory)

        if files:
            file_manager = FileManager(on_list_modified=lambda: None)
            file_manager.set_files(files)
            file_manager.sort_by_date(True)
            file_manager.go_first()
            return self.get_mixed_thumbnail(file_manager.get_current_file(), 
                                            self.default_thumbnail_size)
        else:
            dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, 
                                    self.default_gtk_icon_size)
            return dir_icon.get_pixbuf()

    def get_mixed_thumbnail(self, imagefile, size):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, 
                                self.default_gtk_icon_size)
        ret = dir_icon.get_pixbuf_at_size(size, size)

        # Magic constants needed to fit the embedded thumbnail inside the 
        # directory icon:
        dir_width = 0.88
        dir_height = 0.54
        dir_offset = 0.62

        width, height = imagefile.get_dimensions_to_fit(size * dir_width, 
                                                        size * dir_height)
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
