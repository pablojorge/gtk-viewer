import os
import gtk

from filemanager import FileManager
from filefactory import FileFactory
from imageviewer import ThumbnailViewer

from pdffile import PDFFile
from epubfile import EPUBFile
from videofile import VideoFile

from filescanner import FileScanner

class DirectorySelectorDialog:
    def __init__(self, title, initial_dir, last_targets, callback):
        self.callback = callback

        self.chooser = gtk.FileChooserDialog(title=title,
                                             action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                             buttons=(gtk.STOCK_CANCEL, 
                                                      gtk.RESPONSE_CANCEL,
                                                      gtk.STOCK_OPEN,
                                                      gtk.RESPONSE_OK))

        if initial_dir:
            self.chooser.set_current_folder(initial_dir)

        self.th_viewer = ThumbnailViewer(300)
        widget = self.th_viewer.get_widget()

        ebox = gtk.EventBox()
        ebox.connect("button-press-event", self.on_thumbnail_clicked)
        ebox.connect("scroll-event", self.on_thumbnail_scroll)
        ebox.add(widget)

        self.chooser.set_preview_widget(ebox)
        self.chooser.set_preview_widget_active(True)
        self.chooser.connect("selection-changed", self.on_selection_changed)

        for target in sorted(last_targets):
            self.chooser.add_shortcut_folder(target) 

    def on_selection_changed(self, chooser):
        dirname = chooser.get_preview_filename()
        if dirname:
            scanner = FileScanner()
            files = scanner.get_files_from_dir(dirname)
            if files:
                self.file_manager = FileManager(on_list_empty=lambda: None, 
                                                on_list_modified=lambda: None)
                self.file_manager.set_files(files)
                self.th_viewer.load(self.file_manager.get_current_file())
                self.th_viewer.show()
            else:
                self.th_viewer.hide()
        else:
            self.th_viewer.hide()

    def on_thumbnail_clicked(self, widget, event, data=None):
        self.file_manager.go_forward(1)
        self.th_viewer.load(self.file_manager.get_current_file())

    def on_thumbnail_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            self.file_manager.go_backward(1)
        else:
            self.file_manager.go_forward(1)
        self.th_viewer.load(self.file_manager.get_current_file())

    def run(self):
        response = self.chooser.run()
        selection = self.chooser.get_filename()
        self.chooser.destroy()

        if response == gtk.RESPONSE_OK:
            self.callback(selection)

class FileSelectorDialog:
    def __init__(self, title, initial_dir, initial_filename, callback):
        self.callback = callback

        if initial_filename:
            action = gtk.FILE_CHOOSER_ACTION_SAVE
            button = gtk.STOCK_SAVE
        else:
            action = gtk.FILE_CHOOSER_ACTION_OPEN
            button = gtk.STOCK_OPEN

        self.chooser = gtk.FileChooserDialog(title=title,
                                             action=action,
                                             buttons=(gtk.STOCK_CANCEL, 
                                                      gtk.RESPONSE_CANCEL,
                                                      button,
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
        for ext in (PDFFile.valid_extensions +
                    EPUBFile.valid_extensions +
                    VideoFile.valid_extensions):
            img_filter.add_pattern("*." + ext)
        self.chooser.add_filter(img_filter)

        img_filter = gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_pixbuf_formats()
        self.chooser.add_filter(img_filter)

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

class TargetSelectorDialog(DirectorySelectorDialog):
    def __init__(self, initial_dir, last_targets, callback):
        DirectorySelectorDialog.__init__(self, 
                                         "Specify target directory",
                                         initial_dir,
                                         last_targets,
                                         callback)

class BasedirSelectorDialog(DirectorySelectorDialog):
    def __init__(self, initial_dir, last_targets, callback):
        DirectorySelectorDialog.__init__(self, 
                                         "Specify base directory",
                                         initial_dir,
                                         last_targets,
                                         callback)

class OpenDialog(FileSelectorDialog):
    def __init__(self, initial_dir, callback):
        FileSelectorDialog.__init__(self, title="Open file", 
                                          initial_dir=initial_dir, 
                                          initial_filename=None,
                                          callback=callback)

class RenameDialog(FileSelectorDialog):
    def __init__(self, initial_filename, callback):
        FileSelectorDialog.__init__(self, title="Select new name", 
                                          initial_dir=None,
                                          initial_filename=initial_filename, 
                                          callback=callback)

class AboutDialog:
    def __init__(self, parent):
        self.window = gtk.Dialog(title="About", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_markup("<span size=\"large\">Viewer</span>\n\n" +
                         "Simple Multimedia Viewer")
        self.window.action_area.pack_start(label, True, True, 5)

    def show(self):
        self.window.show_all()

class InfoDialog:
    def __init__(self, parent, message):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_INFO,
                                    gtk.BUTTONS_OK,
                                    message)

    def run(self):
        self.md.run()
        self.md.destroy()

class ErrorDialog:
    def __init__(self, parent, message):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_ERROR,
                                    gtk.BUTTONS_OK,
                                    message)

    def run(self):
        self.md.run()
        self.md.destroy()

class QuestionDialog:
    def __init__(self, parent, question):
        self.md = gtk.MessageDialog(parent, 
                                    gtk.DIALOG_DESTROY_WITH_PARENT, 
                                    gtk.MESSAGE_QUESTION,
                                    gtk.BUTTONS_YES_NO,
                                    question)

    def run(self):
        response = self.md.run()
        self.md.destroy()
        return response == gtk.RESPONSE_YES

