#!/usr/bin/env python

import os
import sys
import gtk

import gobject

from threading import Thread, Lock, Condition

from imagefile import GTKIconImage
from filefactory import FileFactory
from filescanner import FileScanner
from filemanager import FileManager

class GalleryItem:
    def __init__(self, item, size):
        self.item = item
        self.size = size

    def get_scaled_pixbuf(self, image):
        im_dim = image.get_dimensions()

        zw = (float(self.size) / im_dim.get_width()) * 99
        zh = (float(self.size) / im_dim.get_height()) * 99

        factor = min(zw, zh)

        width = int((im_dim.get_width() * factor) / 100)
        height = int((im_dim.get_height() * factor) / 100)

        return image.get_pixbuf_at_size(width, height)

    def append_to(self, liststore):
        pass

    def on_selected(self, gallery):
        pass

class ImageItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def append_to(self, liststore):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        liststore.append([unknown_icon.get_pixbuf(), 
                          self.item.get_basename(),
                          self.item.get_filename()])

    def update_liststore(self, liststore, index):
        print "Updating image at index", index
        iter_ = liststore.get_iter((index,))
        print "Generating pixbuf"
        pixbuf = self.get_scaled_pixbuf(self.item)
        print "Scheduling pixbuf update"
        gobject.idle_add(lambda iter_, pixbuf: liststore.set_value(iter_, 0, pixbuf),
                         iter_,
                         pixbuf)

    def on_selected(self, gallery):
        gallery.callback(self.item.get_filename())
        gallery.close()

class DirectoryItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def append_to(self, liststore):
        dir_icon = GTKIconImage(gtk.STOCK_DIRECTORY, self.size)

        liststore.append([dir_icon.get_pixbuf(),
                          "[%s]" % os.path.basename(self.item),
                          self.item])

    def update_liststore(self, liststore, index):
        print "Updating dir at index", index
        iter_ = liststore.get_iter((index,))
        print "Generating thumbnail for", self.item
        scanner = FileScanner()
        files = scanner.get_files_from_dir(self.item)
        if files:
            file_manager = FileManager(on_list_modified=lambda: None)
            file_manager.set_files(files)
            file_manager.sort_by_date(True)
            file_manager.go_first()
            pixbuf = self.get_scaled_pixbuf(file_manager.get_current_file())
            gobject.idle_add(lambda iter_, pixbuf: liststore.set_value(iter_, 0, pixbuf),
                             iter_,
                             pixbuf)
        else:
            print "Empty dir"
        

    def on_selected(self, gallery):
        gallery.curdir = self.item
        gallery.go_up.set_sensitive(True)
        gallery.update_entries()
        gallery.update_store()

class ThumbnailLoader(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.lock = Lock()
        self.cond = Condition(self.lock)
        self.stopped = False
        self.queue = []

    def run(self):
        print "Thread running!"
        while True:
            job = None
            with self.cond:
                if self.stopped:
                    print "Exiting thread loop"
                    return
                if not self.queue:
                    self.cond.wait()
                else:
                    job, params = self.queue.pop(0)
            if job:
                print "Doing job!"
                job(*params)

    def stop(self):
        print "Thread being stopped..."
        with self.cond:
            self.stopped = True
            self.cond.notify_all()

    def clear(self):
        with self.cond:
            self.queue = []
            self.cond.notify_all()

    def push(self, work):
        with self.cond:
            for job in work:
                self.queue.append(job)
            self.cond.notify_all()

class Gallery:
    DEFAULT_HEIGHT = 600
    THUMB_SIZE = 128
    THUMB_SPACING = 15
    
    def __init__(self, columns, dirname, callback):
        self.callback = callback

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

        # Enable icons in buttons:
        settings = gtk.settings_get_default()
        settings.props.gtk_button_images = True

        # Data initialization:
        self.loader = ThumbnailLoader()
        self.loader.start()

        self.curdir = os.path.realpath(os.path.expanduser(dirname))
        self.items = []

        self.update_entries()
        self.update_store()
        
    def run(self):
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
        self.loader.clear()
        self.liststore.clear()
        work = []

        for index, item in enumerate(self.items):
            item.append_to(self.liststore)
            print "Preparing work for item", index
            work.append((lambda it, st, idx: it.update_liststore(st, idx), (item, self.liststore, index)))

        self.loader.push(work)

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
        self.callback(self.curdir)
        self.close()
        
    def on_cancel_clicked(self, button):
        self.close()

    def close(self):
        print "Stopping thread..."
        self.loader.stop()
        print "Joining thread..."
        self.loader.join()
        print "Destroying window..."
        self.window.destroy()
        
if __name__ == "__main__":
    Gallery(4, sys.argv[1])
    gtk.main()
