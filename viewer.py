#!/usr/bin/env python

import os
import sys

import pygtk
pygtk.require('2.0')
import gtk
import gio

import shutil
import argparse

# XXX separar codigo de manejo de imagen
# XXX separar codigo de manejo de files

# XXX la ventana queda fija al size de la primera imagen
# XXX resetear zoom cuando cambio de imagen (por default ajustar al size de ventana actual)

# XXX hacer zoom in y out con mouse
# XXX si imagen no entra, arrows para moverse
# XXX drag para mover la imagen

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

    def get_filename(self):
        return self.filename

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
    def __init__(self, parent, target_dir, callback):
        self.target_dir = target_dir
        self.callback = callback

        self.window = gtk.Dialog(title="Selector", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("Target directory:")
        self.window.action_area.pack_start(label, True, True, 5)

        entry = gtk.Entry()
        entry.connect("activate", self.on_entry_activate)
        completion = gtk.EntryCompletion()
        liststore = gtk.ListStore(str)
        for directory in sorted(self.__get_options()):
            liststore.append([directory.replace(target_dir, '')])
        completion.set_model(liststore)
        entry.set_completion(completion)
        completion.set_text_column(0)

        self.window.action_area.pack_start(entry, True, True, 5)

    def on_entry_activate(self, entry):
        target = os.path.join(self.target_dir, entry.get_text())
        self.callback(target)
        gtk.Widget.destroy(self.window)

    def __get_options(self):
        for root, dirs, files in os.walk(self.target_dir):
            if root != self.target_dir:
                yield root

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

class FileManager:
    def __init__(self, filelist):
        self.filelist = filelist
        self.index = 0

    def get_current_file(self):
        return ImageFile(self.filelist[self.index])

    def get_current_index(self):
        return self.index

    def get_list_length(self):
        return len(self.filelist)

    def go_next(self):
        self.index += 1
        if self.index >= len(self.filelist):
            self.index = 0

    def go_prev(self):
        self.index -= 1
        if self.index < 0:
            self.index = len(self.filelist) - 1

class ImageViewer:
    def __init__(self):
        self.widget = gtk.Image()
        self.zoom_factor = 1
        self.image_file = None

    def get_widget(self):
        return self.widget

    def get_zoom_factor(self):
        return self.zoom_factor

    def load(self, image_file):
        self.zoom_factor = 1
        self.image_file = image_file
        self.redraw()

    def redraw(self):
        filename = self.image_file.get_filename()

        if filename.endswith(".gif"):
            pixbuf = gtk.gdk.PixbufAnimation(filename)
            self.widget.set_from_animation(pixbuf)
        else:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            width = pixbuf.get_width()
            height = pixbuf.get_height()
            pixbuf = pixbuf.scale_simple(int(width * self.zoom_factor), 
                                         int(height * self.zoom_factor), 
                                         gtk.gdk.INTERP_BILINEAR)
            self.widget.set_from_pixbuf(pixbuf)

class ViewerApp:
    def __init__(self, filelist, target_dir):
        self.file_manager = FileManager(filelist)
        self.image_viewer = ImageViewer()

        self.target_dir = target_dir

        self.current_target = None
        self.undo = []

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_size_request(640, 480)
        self.window.connect("destroy", self.on_destroy)
        self.window.connect("key_press_event", self.on_key_press_event)
        self.window.set_position(gtk.WIN_POS_CENTER)

        self.vbox = gtk.VBox(False, 1)
        self.window.add(self.vbox)
        self.vbox.show()

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.vbox.pack_start(scrolled, True, True, 0)
        scrolled.show()
        # XXX set black background
        #color = gtk.gdk.color_parse("#000000")
        #self.vbox.modify_bg(gtk.STATE_NORMAL, color)
        image_widget = self.image_viewer.get_widget()
        scrolled.add_with_viewport(image_widget)
        image_widget.show()

        self.status_bar = gtk.Statusbar()
        self.vbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        self.reload_viewer()
        self.window.show()

    ## Gtk event handlers
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
    ##

    ## Internal callbacks
    def on_target_selected(self, target):
        current = self.file_manager.get_current_file()

        if not os.path.isdir(target):
            if self.confirm("Create directory %s and move %s there?" % \
                            (target, current.get_basename())):
                os.mkdir(target) # XXX mkdir -p
            else:
                return

        self.current_target = target
        self.update_status("Current", "Press 'r' to repeat '%s'" % target)
        self.move_current()
    ## 

    ## Internal helpers
    def reload_viewer(self):
        self.image_viewer.load(self.file_manager.get_current_file())
        self.refresh_title()

    def refresh_title(self):
        image_file = ImageFile(self.file_manager.get_current_file())

        title = "%s (%s, %d%%, %s, %d/%d)" % (image_file.get_basename(), 
                                              image_file.get_dimensions(), 
                                              self.image_viewer.get_zoom_factor() * 100,
                                              image_file.get_filesize(), 
                                              self.file_manager.get_current_index()+1, 
                                              self.file_manager.get_list_length())
        self.window.set_title(title)
        self.update_status("Info", title)
    ##

    ## action handlers
    def next_image(self):
        self.file_manager.go_next()
        self.reload_viewer()

    def prev_image(self):
        self.file_manager.go_prev()
        self.reload_viewer()

    def apply_category(self):
        selector = SelectorDialog(self.window, self.target_dir, self.on_target_selected)
        selector.show()

    def move_current(self):
        if not self.current_target:
            self.tell_user("There isn't a selected target yet")
            return

        current_image = self.filelist[self.fileindex]
        final_dest = safe_move(current_image, self.current_target)
        print "'%s' moved to '%s'" % (current_image, final_dest)

        self.undo.append((current_image, final_dest))

        self.on_current_altered()

    # XXX rename
    # XXX info dialog
    # XXX question dialog
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
        self.reload_viewer()

    def update_status(self, context, message):
        container_id = self.status_bar.get_context_id(context)
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
        self.reload_viewer()

    def zoom_out(self):
        self.zoom_factor -= 0.1
        self.reload_viewer()

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
            self.reload_viewer()

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

