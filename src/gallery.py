#!/usr/bin/env python

import os
import gtk

from imagefile import GTKIconImage
from filescanner import FileScanner
from filemanager import FileManager

from thumbnail import DirectoryThumbnail

from cache import Cache, cached
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

    @cached()
    def final_thumbnail(self):
        width, height = self.item.get_dimensions_to_fit(self.size, self.size)
        return self.item.get_pixbuf_at_size(width, height)

    def on_selected(self, gallery):
        gallery.on_image_selected(self.item)

class DirectoryItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)
        self.thumbnail = DirectoryThumbnail(item, size)

    def initial_data(self):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        return (self.thumbnail.get_mixed_thumbnail(unknown_icon),
                os.path.basename(self.item),
                self.item)

    def final_thumbnail(self):
        return self.thumbnail.get_pixbuf()

    def on_selected(self, gallery):
        gallery.on_dir_selected(self.item)

class Gallery:
    liststore_cache = Cache(shared=True, 
                            top_cache=FileScanner.cache)

    def __init__(self, title, parent, dirname, callback,
                       dir_selector = False,
                       columns = 4,
                       thumb_size = 256,
                       thumb_spacing = 15,
                       height = 600):
        self.callback = callback
        self.dir_selector = dir_selector
        self.thumb_size = thumb_size

        self.window = gtk.Window()
        self.window.set_size_request(thumb_size * columns + thumb_spacing * columns, 
                                     height)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_resizable(False)
        self.window.set_modal(True)
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_transient_for(parent)
        
        self.window.connect("key_press_event", self.on_key_press_event)

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

        # "Location"/"Filter" bar
        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, False, False, 0)

        label = gtk.Label()
        label.set_text("Location:")
        hbox.pack_start(label, False, False, 0)

        self.location_entry = gtk.Entry()
        self.location_entry.connect("activate", self.on_location_entry_activate)
        hbox.pack_start(self.location_entry, True, True, 0)

        self.filter_entry = gtk.Entry()
        self.filter_entry.connect("activate", self.on_filter_entry_activate)
        hbox.pack_end(self.filter_entry, False, False, 0)

        label = gtk.Label()
        label.set_text("Filter:")
        hbox.pack_end(label, False, False, 0)

        # Iconview
        self.iconview = gtk.IconView()
        self.iconview.set_pixbuf_column(0)
        self.iconview.set_text_column(1)
        self.iconview.set_tooltip_column(2)
        self.iconview.set_selection_mode(gtk.SELECTION_SINGLE)
        self.iconview.set_item_width(self.thumb_size)
        self.iconview.set_spacing(thumb_spacing)
        self.iconview.set_columns(columns)

        self.iconview.connect("selection-changed", self.on_selection_changed)
        self.iconview.connect("item-activated", self.on_item_activated)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(self.iconview)

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
        self.last_filter = ""
        self.items = []

        self.update_model()
        
    def run(self):
        self.window.show_all()
        self.filter_entry.grab_focus()
    
    def get_items_for_dir(self, directory, filter_):
        items = []

        # Obtain the directories first:
        scanner = FileScanner()

        for dir_ in scanner.get_dirs_from_dir(directory):
            if filter_ and not filter_.lower() in dir_.lower():
                continue
            items.append(DirectoryItem(dir_, self.thumb_size/2))
    
        # Now the files:
        files = scanner.get_files_from_dir(directory)
        
        file_manager = FileManager(on_list_modified=lambda: None)
        file_manager.set_files(files)
        file_manager.sort_by_date(True)
        file_manager.go_first()

        for _ in range(file_manager.get_list_length()):
            current_file = file_manager.get_current_file()
            if not filter_ or filter_.lower() in current_file.get_basename().lower():
                items.append(ImageItem(current_file, self.thumb_size/2))
            file_manager.go_forward(1)

        return items

    @cached(liststore_cache)
    def build_store(self, directory, filter_):
        liststore = gtk.ListStore(gtk.gdk.Pixbuf, str, str)

        # Retrieve the items for this dir:
        items = self.get_items_for_dir(directory, filter_)

        # And fill the store:
        for index, item in enumerate(items):
            # Load the inital data:
            liststore.append(item.initial_data())

        return items, liststore

    def update_model(self, filter_=""):
        self.loader.clear()

        items, liststore = self.build_store(self.curdir, filter_)

        for index, item in enumerate(items):
            # Schedule an update on this item:
            self.loader.push((self.update_item_thumbnail, (liststore, index, item)))

        # Update the items list:
        self.items = items
        # Associate the new liststore to the iconview:
        self.iconview.set_model(liststore)
        # Update the curdir entry widget:
        self.location_entry.set_text(self.curdir)

    # This is done in a separate thread:
    def update_item_thumbnail(self, liststore, index, item):
        pixbuf = item.final_thumbnail()
        return (self.update_store_entry, (liststore, index, pixbuf))

    # This is requested to be done by the main thread:
    def update_store_entry(self, liststore, index, pixbuf):
        iter_ = liststore.get_iter((index,))
        liststore.set_value(iter_, 0, pixbuf)

    def on_key_press_event(self, widget, event, data=None):
        key_name = gtk.gdk.keyval_name(event.keyval)
        #print "gallery - key pressed:", key_name

        bindings = {
            "Escape" : self.close,
            "Up" : lambda: self.on_go_up(None),
        }

        if key_name in bindings:
            bindings[key_name]()
            return True

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
            self.filter_entry.grab_focus()
        else:
            entry.set_text(self.curdir)

    def on_filter_entry_activate(self, entry):
        if (not entry.get_text() and 
            not self.last_filter and 
            self.dir_selector):
            self.callback(self.curdir)
            self.close()
            return

        # Restrict the entries to those containing the filter:
        self.update_model(entry.get_text())
        self.last_filter = entry.get_text()

        # If only one item matches, simulate it's been selected:
        if len(self.items) == 1:
            self.items[0].on_selected(self)

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

    def on_image_selected(self, item):
        self.callback(item.get_filename())
        self.close()

    def on_dir_selected(self, item):
        scanner = FileScanner()
        dirs = scanner.get_dirs_from_dir(item)

        if self.dir_selector and not dirs:
            self.callback(item)
            self.close()
            return

        self.curdir = item
        self.go_up.set_sensitive(True)
        self.update_model()
        self.last_filter = ""
        self.filter_entry.set_text("")
        self.filter_entry.grab_focus()

    def on_ok_clicked(self, button):
        if not self.dir_selector:
            return
        self.callback(self.curdir)
        self.close()
        
    def on_cancel_clicked(self, button):
        self.close()

    def close(self):
        self.loader.stop()
        self.loader.join()
        self.window.destroy()
        
