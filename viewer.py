#!/usr/bin/env python

import os
import sys

import pygtk
pygtk.require('2.0')
import gtk
import gio

import shutil
import argparse

# XXX la ventana queda fija al size de la primera imagen
# XXX resetear zoom cuando cambio de imagen (por default ajustar al size de ventana actual)

# XXX separar codigo de manejo de imagen
# XXX separar codigo de manejo de files

# XXX hacer zoom in y out con mouse
# XXX si imagen no entra, arrows para moverse
# XXX drag para mover la imagen

def get_dirs(directory):
    for root, dirs, files in os.walk(directory):
        if root != directory:
            yield root

def safe_move(filename, target):
    candidate = os.path.split(filename)[-1]

    index = 0
    while os.path.isfile(os.path.join(target, candidate)):
        name = os.path.split(''.join(filename.split('.')[:-1]))[-1]
        ext = filename.split('.')[-1]
        index += 1
        candidate = "%s (%d).%s" % (name, index, ext)

    final = os.path.join(target, candidate)
    shutil.move(filename, final)

    return final

class ImageDimensions:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def __str__(self):
        return "%dx%d" % (self.width, self.height)

class FileSize:
    def __init__(self, size):
        self.size = size

    def get_size(self):
        return self.size

    def __str__(self):
        if self.size < 1024:
            return "%d bytes" % self.size
        elif self.size < (1024*1024):
            return "%.2f Kb" % (self.size/1024)
        else:
            return "%.2f Mb" % (self.size/(1024*1024))

class ImageFile:
    def __init__(self, filename):
        self.filename = filename

    def get_basename(self):
        return os.path.split(self.filename)[-1]

    def get_dimensions(self):
        pixbuf = gtk.gdk.pixbuf_new_from_file(self.filename)
        return ImageDimensions(pixbuf.get_width(), pixbuf.get_height())

    def get_filesize(self):
        stat = os.stat(self.filename)
        size = stat.st_size
        return FileSize(size)

class SelectorDialog:
    def __init__(self, parent, target_dir, move_callback):
        self.target_dir = target_dir
        self.move_callback = move_callback

        self.window = gtk.Dialog(title="Selector", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("Target directory:")
        self.window.action_area.pack_start(label, True, True, 5)

        entry = gtk.Entry()
        entry.connect("activate", self.on_entry_activate)
        completion = gtk.EntryCompletion()
        liststore = gtk.ListStore(str)
        for directory in sorted(get_dirs(target_dir)):
            liststore.append([directory.replace(target_dir, '')])
        completion.set_model(liststore)
        entry.set_completion(completion)
        completion.set_text_column(0)

        self.window.action_area.pack_start(entry, True, True, 5)

    def on_entry_activate(self, entry):
        target = os.path.join(self.target_dir, entry.get_text())
        self.move_callback(target)
        gtk.Widget.destroy(self.window)

    def show(self):
        self.window.show_all()

class HelpDialog:
    def __init__(self, parent, text):
        self.window = gtk.Dialog(title="Help", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text(text)
        self.window.action_area.pack_start(label, True, True, 5)

    def show(self):
        self.window.show_all()

class ViewerApp:
    def __init__(self, filelist, target_dir):
        self.filelist = filelist
        self.target_dir = target_dir
        self.fileindex = 0

        self.width = -1
        self.height = -1
        self.zoom_factor = 1
        self.current_target = None
        self.undo = []

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        first_image = ImageFile(filelist[0])
        dimensions = first_image.get_dimensions()
        self.window.set_size_request(dimensions.get_width() + 10, 
                                     dimensions.get_height() + 25)
        self.window.connect("destroy", self.on_destroy)
        self.window.connect("delete_event", self.on_delete_event)
        self.window.connect("key_press_event", self.on_key_press_event)
        #self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)

        self.vbox = gtk.VBox(False, 1)
        self.window.add(self.vbox)
        self.vbox.show()

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(scrolled, True, True, 0)
        scrolled.show()
        self.image = gtk.Image()
        #color = gtk.gdk.color_parse("#000000")
        #self.vbox.modify_bg(gtk.STATE_NORMAL, color)
        self.image.connect("expose_event", self.on_image_expose)
        scrolled.add_with_viewport(self.image)
        self.image.show()

        self.status_bar = gtk.Statusbar()
        self.vbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        self.refresh_image()
        self.window.show()

    def on_image_expose(self, widget, event, data=None):
        self.width = event.area.width
        self.height = event.area.height
        #print "width:", self.width
        #print "height:", self.height

    def on_delete_event(self, widget, event, data=None):
        return False

    def on_destroy(self, widget):
        gtk.main_quit()

    def on_key_press_event(self, widget, event, data=None):
        key_action = {
            "q" : self.quit_app,
            "Escape" : self.quit_app,
            "space" : self.next_image,
            "Right" : self.next_image,
            "Return" : self.next_image,
            "BackSpace" : self.prev_image,
            "Left" : self.prev_image,
            "Down" : self.apply_category,
            "Tab" : self.apply_category,
            "r" : self.move_current,
            "u" : self.undo_last,
            "h" : self.show_help,
            "Delete" : self.delete_image,
            "KP_Add" : self.zoom_in,
            "plus" : self.zoom_in,
            "KP_Subtract" : self.zoom_out,
            "minus" : self.zoom_out,
        }

        key_name = gtk.gdk.keyval_name(event.keyval)
        print "key pressed:", key_name

        if key_name in key_action:
            key_action[key_name]()

    def refresh_image(self):
        filename = self.filelist[self.fileindex]

        if filename.endswith(".gif"):
            pixbuf = gtk.gdk.PixbufAnimation(filename)
            self.image.set_from_animation(pixbuf)
        else:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            width = pixbuf.get_width()
            height = pixbuf.get_height()
            pixbuf = pixbuf.scale_simple(int(width * self.zoom_factor), 
                                         int(height * self.zoom_factor), 
                                         gtk.gdk.INTERP_BILINEAR)
            self.image.set_from_pixbuf(pixbuf)

        self.refresh_title()

    def refresh_title(self):
        image_file = ImageFile(self.filelist[self.fileindex])

        title = "%s (%s, %d%%, %s, %d/%d)" % (image_file.get_basename(), 
                                              image_file.get_dimensions(), 
                                              int(self.zoom_factor * 100),
                                              image_file.get_filesize(), 
                                              self.fileindex+1, 
                                              len(self.filelist))
        self.window.set_title(title)

    def next_image(self):
        self.fileindex += 1
        if self.fileindex >= len(self.filelist):
            self.fileindex = 0
        self.refresh_image()

    def prev_image(self):
        self.fileindex -= 1
        if self.fileindex < 0:
            self.fileindex = len(self.filelist) - 1
        self.refresh_image()

    def apply_category(self):
        selector = SelectorDialog(self.window, self.target_dir, self.move_callback)
        selector.show()

    def move_callback(self, target):
        filename = self.filelist[self.fileindex]
        basename = os.path.split(filename)[-1]

        if not os.path.isdir(target):
            if self.confirm("Create directory %s and move %s there?" % (target, basename)):
                os.mkdir(target) # XXX mkdir -p
            else:
                return

        self.current_target = target
        self.update_status("Press 'r' to repeat '%s'" % target)
        self.move_current()

    def move_current(self):
        if not self.current_target:
            self.tell_user("There isn't a selected target yet")
            return

        current_image = self.filelist[self.fileindex]
        final_dest = safe_move(current_image, self.current_target)
        print "'%s' moved to '%s'" % (current_image, final_dest)

        self.undo.append((current_image, final_dest))

        self.on_current_altered()

    def show_help(self):
        helpd = HelpDialog(self.window, "<help>") # XXX
        helpd.show()

    def undo_last(self):
        if not self.undo:
            self.tell_user("Nothing to undo!")
            return

        orig_path, moved_path = self.undo.pop() 
        shutil.move(moved_path, orig_path)
        print "'%s' restored from '%s'" % (orig_path, moved_path)
        self.filelist.insert(self.fileindex, orig_path)
        self.refresh_image()

    def update_status(self, message):
        container_id = self.status_bar.get_context_id("Statusbar")
        self.status_bar.pop(container_id)
        self.status_bar.push(container_id, message)

    def tell_user(self, message):
        md = gtk.MessageDialog(self.window, 
                               gtk.DIALOG_DESTROY_WITH_PARENT, 
                               gtk.MESSAGE_INFO,
                               gtk.BUTTONS_OK,
                               message)
        md.run()
        md.destroy()

    def confirm(self, question):
        md = gtk.MessageDialog(self.window, 
                               gtk.DIALOG_DESTROY_WITH_PARENT, 
                               gtk.MESSAGE_QUESTION,
                               gtk.BUTTONS_YES_NO,
                               question)
        response = md.run()
        md.destroy()

        return response == gtk.RESPONSE_YES

    def delete_image(self):
        filename = self.filelist[self.fileindex]
        basename = os.path.split(filename)[-1]

        if self.confirm("Send '%s' to the trash?" % basename):
            #print "Deleting %s..." % filename

            # Delete the file:
            gfile = gio.File(path=filename)
            gfile.trash()

            self.on_current_altered()

    def zoom_in(self):
        self.zoom_factor += 0.1
        self.refresh_image()

    def zoom_out(self):
        self.zoom_factor -= 0.1
        self.refresh_image()

    def on_current_altered(self):
        # Eliminate file from list:
        del self.filelist[self.fileindex]

        # Exit if there are no more files:
        if not self.filelist:
            self.tell_user("No more files, exiting")
            self.quit_app()
        else:
            if self.fileindex >= len(self.filelist):
                self.fileindex = len(self.filelist) - 1

            # Refresh the image:
            self.refresh_image()

    def quit_app(self):
        gtk.Widget.destroy(self.window)

    def main(self):
        gtk.main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('files', help='Files to organize', metavar='FILE', nargs='+')
    parser.add_argument('target', help='Target directory', metavar='TARGET')

    args = parser.parse_args()

    app = ViewerApp(args.files, args.target)
    app.main()

