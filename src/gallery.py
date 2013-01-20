#!/usr/bin/env python

import os
import sys
import gtk

from imagefile import GTKIconImage
from filefactory import FileFactory
from filescanner import FileScanner

class GalleryItem:
    def __init__(self, item, size):
        self.item = item
        self.size = size

    def append_to(self, liststore):
        pass

    def on_selected(self, gallery):
        pass

class ImageItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def append_to(self, liststore):
        im_dim = self.item.get_dimensions()

        zw = (float(self.size) / im_dim.get_width()) * 99
        zh = (float(self.size) / im_dim.get_height()) * 99

        factor = min(zw, zh)

        width = int((im_dim.get_width() * factor) / 100)
        height = int((im_dim.get_height() * factor) / 100)

        liststore.append([self.item.get_pixbuf_at_size(width, height), 
                          self.item.get_basename(),
                          self.item.get_filename()])

    def on_selected(self, gallery):
        self.item.external_open()

class DirectoryItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def append_to(self, liststore):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, self.size)

        liststore.append([dir_icon.get_pixbuf(),
                          os.path.basename(self.item),
                          self.item])

    def on_selected(self, gallery):
        gallery.curdir = self.item
        gallery.go_up.set_sensitive(True)
        gallery.update_entries()
        gallery.update_store()

class Gallery:
    DEFAULT_HEIGHT = 600
    THUMB_SIZE = 128
    THUMB_SPACING = 15
    
    def __init__(self, columns, dirname):
        self.window = gtk.Window()
        self.window.set_size_request(self.THUMB_SIZE * columns + 
                                self.THUMB_SPACING * columns, 
                                self.DEFAULT_HEIGHT)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_resizable(False) # para dialog, para galeria deberia ser true
        
        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

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

        self.liststore = gtk.ListStore(gtk.gdk.Pixbuf, str, str)

        iconview = gtk.IconView()
        iconview.set_model(self.liststore)
        iconview.set_pixbuf_column(0)
        iconview.set_text_column(1)
        iconview.set_tooltip_column(2)
        iconview.set_selection_mode(gtk.SELECTION_SINGLE)
        iconview.set_item_width(self.THUMB_SIZE)
        iconview.set_columns(columns)

        iconview.connect("selection-changed", self.on_selection_changed)
        iconview.connect("item-activated", self.on_item_activated)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(iconview)

        vbox.pack_start(scrolled, True, True, 0)

        buttonbar = gtk.HBox(False, 0)

        button = gtk.Button(stock=gtk.STOCK_OK)
        button.connect("clicked", self.on_ok_clicked)
        buttonbar.pack_end(button, False, False, 5)

        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.connect("clicked", self.on_cancel_clicked)
        buttonbar.pack_end(button, False, False, 0)

        vbox.pack_start(buttonbar, False, False, 5)

        # Data initialization:
        self.curdir = dirname
        self.items = []

        self.update_entries()
        self.update_store()
        
        self.window.connect("destroy", lambda w: gtk.main_quit())
        
        self.window.show_all()
    
    def update_entries(self):
        self.items = []

        scanner = FileScanner()

        for directory in scanner.get_dirs_from_dir(self.curdir):
            self.items.append(DirectoryItem(directory, self.THUMB_SIZE/2))
    
        for filename in scanner.get_files_from_dir(self.curdir):
            imgfile = FileFactory.create(filename)
            self.items.append(ImageItem(imgfile, self.THUMB_SIZE/2))

    def update_store(self):
        self.liststore.clear()

        for item in self.items:
            item.append_to(self.liststore)
        
    def on_go_up(self, widget):
        self.curdir = os.path.split(self.curdir)[0]
        if self.curdir == "/":
            self.go_up.set_sensitive(False)
        self.update_entries()
        self.update_store()

    def on_go_home(self, widget):
        self.curdir = os.path.realpath(os.path.expanduser('~'))
        self.go_up.set_sensitive(True)
        self.update_entries()
        self.update_store()

    def on_selection_changed(self, iconview):
        selected = iconview.get_selected_items()

        if not selected:
            return

        index = selected[0][0]
        item = self.items[index]
        iconview.unselect_all()

        item.on_selected(self)
        
    def on_item_activated(self, iconview, path):
        print "on_item_activated", path

    def on_ok_clicked(self, button):
        print "User chose", self.curdir
        self.window.destroy()
        
    def on_cancel_clicked(self, button):
        self.window.destroy()
        
Gallery(4, sys.argv[1])
gtk.main()
