#!/usr/bin/env python

import os
import gtk

from imagefile import GTKIconImage
from filescanner import FileScanner
from filemanager import FileManager

from worker import Worker

class GalleryItem:
    def __init__(self, item, size):
        self.item = item
        self.size = size

    def initial_data(self):
        pass

    def final_thumbnail(self):
        pass

    def on_selected(self, gallery):
        pass

class ImageItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def initial_data(self):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        return (unknown_icon.get_pixbuf(), 
                self.item.get_basename(),
                self.item.get_filename())

    def final_thumbnail(self):
        width, height = self.item.get_dimensions_to_fit(self.size, self.size)
        return self.item.get_pixbuf_at_size(width, height)

    def on_selected(self, gallery):
        gallery.callback(self.item.get_filename())
        gallery.close()

class DirectoryItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def initial_data(self):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        return (self.get_mixed_thumbnail(unknown_icon),
                os.path.basename(self.item),
                self.item)

    def final_thumbnail(self):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, self.size)

        scanner = FileScanner()
        files = scanner.get_files_from_dir(self.item)

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

    def on_selected(self, gallery):
        gallery.curdir = self.item
        gallery.go_up.set_sensitive(True)
        gallery.update_model()

class Gallery:
    def __init__(self, title, parent, dirname, callback,
                       columns = 4,
                       thumb_size = 256,
                       thumb_spacing = 15,
                       height = 600):
        self.callback = callback
        self.thumb_size = thumb_size

        self.window = gtk.Window()
        self.window.set_size_request(thumb_size * columns + thumb_spacing * columns, 
                                     height)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_resizable(False)
        self.window.set_modal(True)
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_transient_for(parent)
        
        # XXX escape q to exit dialog? / Enter default
        # XXX type to restrict entries (for entry in model remove if not text in str)

        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

        # Toolbar
        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)

        vbox.pack_start(toolbar, False, False, 0)

        button = gtk.ToolButton(gtk.STOCK_HOME)
        button.connect("clicked", self.on_go_home)
        button.set_is_important(True)
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GO_UP)
        button.connect("clicked", self.on_go_up)
        button.set_is_important(True)
        toolbar.insert(button, -1)
        self.go_up = button

        # "Location" bar
        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_text("Location:")
        hbox.pack_start(label, False, False, 0)
        self.location_entry = gtk.Entry()
        self.location_entry.connect("activate", self.on_location_entry_activate)
        vbox.pack_start(hbox, False, False, 0)

        # Iconview
        self.liststore = gtk.ListStore(gtk.gdk.Pixbuf, str, str)

        iconview = gtk.IconView()
        iconview.set_model(self.liststore)
        iconview.set_pixbuf_column(0)
        iconview.set_text_column(1)
        iconview.set_tooltip_column(2)
        iconview.set_selection_mode(gtk.SELECTION_SINGLE)
        iconview.set_item_width(self.thumb_size)
        iconview.set_spacing(thumb_spacing)
        iconview.set_columns(columns)

        iconview.connect("selection-changed", self.on_selection_changed)
        iconview.connect("item-activated", self.on_item_activated)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(iconview)

        vbox.pack_start(scrolled, True, True, 0)

        # Buttonbar
        buttonbar = gtk.HBox(False, 0)

        button = gtk.Button(stock=gtk.STOCK_OK)
        button.connect("clicked", self.on_ok_clicked)
        buttonbar.pack_end(button, False, False, 5)

        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.connect("clicked", self.on_cancel_clicked)
        buttonbar.pack_end(button, False, False, 0)

        vbox.pack_start(buttonbar, False, False, 5)

        # Enable icons in buttons:
        settings = gtk.settings_get_default()
        settings.props.gtk_button_images = True

        # Data initialization:
        self.loader = Worker()
        self.loader.start()

        self.curdir = os.path.realpath(os.path.expanduser(dirname))
        self.items = []

        self.update_model()
        
    def run(self):
        self.window.show_all()
    
    def update_model(self):
        self.loader.clear()
        self.liststore.clear()

        self.items = []

        # Obtain the directories first:
        scanner = FileScanner()

        for directory in scanner.get_dirs_from_dir(self.curdir):
            self.items.append(DirectoryItem(directory, self.thumb_size/2))
    
        # Now the files:
        files = scanner.get_files_from_dir(self.curdir)
        
        file_manager = FileManager(on_list_modified=lambda: None)
        file_manager.set_files(files)
        file_manager.sort_by_date(True)
        file_manager.go_first()

        for _ in range(file_manager.get_list_length()):
            self.items.append(ImageItem(file_manager.get_current_file(), 
                                        self.thumb_size/2))
            file_manager.go_forward(1)

        # And now fill the store:
        for index, item in enumerate(self.items):
            # Load the inital data:
            self.liststore.append(item.initial_data())
            # And schedule an update on this item:
            self.loader.push((self.update_item_thumbnail, (index, item)))

        # And update the curdir entry widget:
        self.location_entry.set_text(self.curdir)

    # This is done in a separate thread:
    def update_item_thumbnail(self, index, item):
        pixbuf = item.final_thumbnail()
        return (self.update_store_entry, (index, pixbuf))

    # This is requested to be done by the main thread:
    def update_store_entry(self, index, pixbuf):
        iter_ = self.liststore.get_iter((index,))
        self.liststore.set_value(iter_, 0, pixbuf)

    def on_go_up(self, widget):
        self.curdir = os.path.split(self.curdir)[0]
        if self.curdir == "/":
            self.go_up.set_sensitive(False)
        self.update_model()

    def on_go_home(self, widget):
        self.curdir = os.path.realpath(os.path.expanduser('~'))
        self.go_up.set_sensitive(True)
        self.update_model()

    def on_location_entry_activate(self, entry):
        directory = entry.get_text()
        if os.path.isdir(directory):
            self.curdir = directory
            self.update_model()
        else:
            entry.set_text(self.curdir)

    def on_selection_changed(self, iconview):
        selected = iconview.get_selected_items()

        if not selected:
            return

        index = selected[0][0]
        item = self.items[index]
        iconview.unselect_all()

        item.on_selected(self)
        
    def on_item_activated(self, iconview, path):
        pass

    def on_ok_clicked(self, button):
        self.callback(self.curdir)
        self.close()
        
    def on_cancel_clicked(self, button):
        self.close()

    def close(self):
        self.loader.stop()
        self.loader.join()
        self.window.destroy()
        
