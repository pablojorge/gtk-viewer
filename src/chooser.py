import os
import gtk

from filefactory import FileFactory
from imageviewer import ThumbnailViewer

from archivefile import ArchiveFile
from pdffile import PDFFile
from epubfile import EPUBFile
from videofile import VideoFile

from gallery import GallerySelector

class FileSelectorDialogGTK:
    def __init__(self, title, initial_dir, initial_filename, callback):
        self.callback = callback

        self.chooser = gtk.FileChooserDialog(title=title,
                                             action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                             buttons=(gtk.STOCK_CANCEL, 
                                                      gtk.RESPONSE_CANCEL,
                                                      gtk.STOCK_SAVE,
                                                      gtk.RESPONSE_OK))

        if initial_dir:
            self.chooser.set_current_folder(initial_dir)

        if initial_filename:
            self.chooser.set_filename(initial_filename)

        self.th_viewer = ThumbnailViewer(300)
        widget = self.th_viewer.get_widget()

        self.chooser.set_preview_widget(widget)
        self.chooser.set_preview_widget_active(True)
        self.chooser.connect("selection-changed", self.on_selection_changed)

        img_filter = gtk.FileFilter()
        img_filter.set_name("All supported files")
        img_filter.add_pixbuf_formats()
        for ext in (ArchiveFile.valid_extensions +
                    PDFFile.valid_extensions +
                    EPUBFile.valid_extensions +
                    VideoFile.valid_extensions):
            img_filter.add_pattern("*." + ext)
        self.chooser.add_filter(img_filter)

        img_filter = gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_pixbuf_formats()
        self.chooser.add_filter(img_filter)

        self.add_filter("Archive Files", ArchiveFile.valid_extensions)
        self.add_filter("PDF Files", PDFFile.valid_extensions)
        self.add_filter("EPub Files", EPUBFile.valid_extensions)
        self.add_filter("Video Files", VideoFile.valid_extensions)

    def add_filter(self, name, extensions):
        filter_ = gtk.FileFilter()
        filter_.set_name(name)
        for ext in extensions:
            filter_.add_pattern("*." + ext)
        self.chooser.add_filter(filter_)

    def on_selection_changed(self, chooser):
        filename = chooser.get_preview_filename()
        if filename:
            if os.path.isfile(filename):
                self.th_viewer.load(FileFactory.create(filename))
                self.th_viewer.show()
            else:
                self.th_viewer.hide()
        else:
            self.th_viewer.hide()

    def run(self):
        response = self.chooser.run()
        selection = self.chooser.get_filename()
        self.chooser.destroy()

        if response == gtk.RESPONSE_OK:
            self.callback(selection)

class DirectorySelectorDialogCustom:
    def __init__(self, title, parent, initial_dir, last_targets, callback):
        self.gallery = GallerySelector(title, parent, initial_dir, last_targets, 
                                       on_file_selected=lambda f: None, 
                                       on_dir_selected=lambda d, r: callback(d), 
                                       dir_selector=True)

    def run(self):
        self.gallery.run()

class FileSelectorDialogCustom:
    def __init__(self, title, parent, initial_dir, initial_filename, on_file_selected, on_dir_selected):
        self.gallery = GallerySelector(title, parent, initial_dir, [], on_file_selected, on_dir_selected)

    def run(self):
        self.gallery.run()

class DirectorySelectorDialog(DirectorySelectorDialogCustom):
    pass

class FileSelectorDialog(FileSelectorDialogCustom):
    pass

class TargetSelectorDialog(DirectorySelectorDialog):
    def __init__(self, parent, initial_dir, last_targets, callback):
        DirectorySelectorDialog.__init__(self, 
                                         "Specify target directory",
                                         parent=parent,
                                         initial_dir=initial_dir,
                                         last_targets=last_targets,
                                         callback=callback)

class BasedirSelectorDialog(DirectorySelectorDialog):
    def __init__(self, parent, initial_dir, last_targets, callback):
        DirectorySelectorDialog.__init__(self, 
                                         "Specify base directory",
                                         parent=parent,
                                         initial_dir=initial_dir,
                                         last_targets=last_targets,
                                         callback=callback)

class OpenDialog(FileSelectorDialog):
    def __init__(self, parent, initial_dir, on_file_selected, on_dir_selected):
        FileSelectorDialog.__init__(self, title="Open file", 
                                          parent=parent,
                                          initial_dir=initial_dir, 
                                          initial_filename=None,
                                          on_file_selected=on_file_selected,
                                          on_dir_selected=on_dir_selected)

class RenameDialog(FileSelectorDialogGTK):
    def __init__(self, parent, initial_filename, callback):
        FileSelectorDialogGTK.__init__(self, title="Select new name", 
                                             initial_dir=None,
                                             initial_filename=initial_filename, 
                                             callback=callback)

class OutputDialog(FileSelectorDialogGTK):
    def __init__(self, parent, callback):
        FileSelectorDialogGTK.__init__(self, title="Select output filename", 
                                             initial_dir=None,
                                             initial_filename=None, 
                                             callback=callback)

