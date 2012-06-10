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

# XXX hacer zoom in y out con mouse
# XXX drag para mover la imagen

# XXX si imagen no entra, arrows para moverse

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

class File:
    def __init__(self, filename):
        self.filename = filename

    def get_filename(self):
        return self.filename

    def get_dirname(self):
        return os.path.split(self.filename)[0]

    def get_basename(self):
        return os.path.split(self.filename)[-1]

    def get_filesize(self):
        stat = os.stat(self.filename)
        size = stat.st_size
        return FileSize(size)

    def rename(self, new_name):
        shutil.move(self.filename, new_name)
        self.filename = new_name

    def safe_move(self, target):
        candidate = os.path.split(self.filename)[-1]

        index = 0
        while os.path.isfile(os.path.join(target, candidate)):
            name = os.path.split(''.join(filename.split('.')[:-1]))[-1]
            ext = filename.split('.')[-1]
            index += 1
            candidate = "%s (%d).%s" % (name, index, ext)

        final = os.path.join(target, candidate)
        self.rename(final)

class ImageFile(File):
    def __init__(self, filename):
        File.__init__(self, filename)

    def get_dimensions(self):
        pixbuf = gtk.gdk.pixbuf_new_from_file(self.get_filename())
        return ImageDimensions(pixbuf.get_width(), pixbuf.get_height())

class FileManager:
    def __init__(self, filelist, on_list_empty, on_list_modified):
        self.filelist = map(ImageFile, filelist)
        self.index = 0

        self.on_list_empty = on_list_empty
        self.on_list_modified = on_list_modified

    def get_current_file(self):
        return self.filelist[self.index]

    def get_current_index(self):
        return self.index

    def get_list_length(self):
        return len(self.filelist)

    def go_next(self):
        self.index += 1
        if self.index >= len(self.filelist):
            self.index = 0
        self.on_list_modified()

    def go_prev(self):
        self.index -= 1
        if self.index < 0:
            self.index = len(self.filelist) - 1
        self.on_list_modified()

    def rename_current(self, new_name):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_name = current.get_basename()
        current.rename(os.path.join(current.get_dirname(), new_name))
        self.on_list_modified()

        def undo_action():
            current.rename(os.path.join(current.get_dirname(), orig_name))
            self.index = orig_index # XXX podria no existir mas
            self.on_list_modified()

        return undo_action

    def move_current(self, target):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_filename = current.get_filename()
        current.safe_move(target)
        new_filename = current.get_filename()
        self.on_current_eliminated()

        def undo_action():
            restored = ImageFile(new_filename)
            restored.rename(orig_filename)
            self.filelist.insert(orig_index, restored)
            self.index = orig_index # XXX podria ser out of bounds
            self.on_list_modified()

        return undo_action

    def delete_current(self):
        gfile = gio.File(path=self.get_current_file().get_filename())
        gfile.trash()

        self.on_current_eliminated()

    # Internal helpers:
    def on_current_eliminated(self):
        del self.filelist[self.index]

        if not self.filelist:
            self.on_list_empty()
        else:
            if self.index >= len(self.filelist):
                self.index = len(self.filelist) - 1
            self.on_list_modified()

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

class RenameDialog:
    def __init__(self, parent, basename, callback):
        self.basename = basename
        self.callback = callback

        self.window = gtk.Dialog(title="Rename", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("New name:")
        self.window.action_area.pack_start(label, True, True, 5)

        entry = gtk.Entry()
        entry.connect("activate", self.on_entry_activate)
        entry.set_text(basename)
        #entry.select_region(0, entry.get_text().rindex('.')) # XXX ???

        self.window.action_area.pack_start(entry, True, True, 5)

    def on_entry_activate(self, entry):
        if entry.get_text() != self.basename:
            self.callback(entry.get_text())
        gtk.Widget.destroy(self.window)

    def show(self):
        self.window.show_all()

class HelpDialog:
    def __init__(self, parent, bindings):
        self.window = gtk.Dialog(title="Help", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text(self.__build_help(bindings))
        self.window.action_area.pack_start(label, True, True, 5)

    def __build_help(self, bindings):
        actions = []
        for key, action in bindings.iteritems():
            actions.append("%s -> %s" % (key, action.__name__))
        return "\n".join(actions)

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

    def adjust_zoom(self, delta):
        self.zoom_factor += delta
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
        self.file_manager = FileManager(filelist,
                                        self.on_list_empty,
                                        self.on_list_modified)
        self.image_viewer = ImageViewer()

        self.target_dir = target_dir

        self.last_target = None
        self.undo_queue = []

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
        key_name = gtk.gdk.keyval_name(event.keyval)
        #print "key pressed:", key_name

        bindings = self.get_key_bindings()

        if key_name in bindings:
            bindings[key_name]()
    ##

    ## Internal callbacks
    def on_target_selected(self, target):
        current = self.file_manager.get_current_file()

        if not os.path.isdir(target):
            if QuestionDialog(self.window, 
                              "Create directory %s and move %s there?" % \
                              (target, current.get_basename())).run():
                os.mkdir(target) # XXX mkdir -p
            else:
                return

        self.last_target = target
        self.undo_queue.append(self.file_manager.move_current(target))

    def on_new_name_selected(self, new_name):
        current = self.file_manager.get_current_file()

        self.undo_queue.append(self.file_manager.rename_current(new_name))

    def on_list_empty(self):
        InfoDialog(self.window, "No more files, exiting").run()
        self.quit_app()

    def on_list_modified(self):
        self.reload_viewer()
    ## 

    ## Internal helpers
    def reload_viewer(self):
        self.image_viewer.load(self.file_manager.get_current_file())
        self.refresh_info()

    def refresh_info(self):
        self.refresh_title()
        self.refresh_status()

    def refresh_title(self):
        image_file = self.file_manager.get_current_file()
        self.window.set_title(image_file.get_basename())

    def refresh_status(self):
        image_file = self.file_manager.get_current_file()

        status = "%s pixels %d%% %s %d/%d" % (image_file.get_dimensions(), 
                                              self.image_viewer.get_zoom_factor() * 100,
                                              image_file.get_filesize(), 
                                              self.file_manager.get_current_index() + 1, 
                                              self.file_manager.get_list_length())

        if self.last_target:
            last = self.last_target.replace(self.target_dir, '')
            status += " (press 'r' to repeat '%s')" % last

        container_id = self.status_bar.get_context_id("Status Bar")
        self.status_bar.pop(container_id)
        self.status_bar.push(container_id, status)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        return {
            ## Generic actions:
            "q" : self.quit_app,
            "Escape" : self.quit_app,
            "h" : self.show_help,
            ## Files navigation:
            "space" : self.next_image,
            "Right" : self.next_image,
            "Return" : self.next_image,
            "BackSpace" : self.prev_image,
            "Left" : self.prev_image,
            ## Files manipulation:
            "Down" : self.apply_category,
            "Tab" : self.apply_category,
            "F2" : self.rename_current,
            "r" : self.repeat_selection,
            "u" : self.undo_last,
            "Delete" : self.delete_image,
            ## Zoom:
            "KP_Add" : self.zoom_in,
            "plus" : self.zoom_in,
            "KP_Subtract" : self.zoom_out,
            "minus" : self.zoom_out,
        }

    ## action handlers
    def quit_app(self):
        gtk.Widget.destroy(self.window)

    def show_help(self):
        helpd = HelpDialog(self.window, self.get_key_bindings())
        helpd.show()

    def next_image(self):
        self.file_manager.go_next()

    def prev_image(self):
        self.file_manager.go_prev()

    def apply_category(self):
        selector = SelectorDialog(self.window, self.target_dir, self.on_target_selected)
        selector.show()

    def rename_current(self):
        basename = self.file_manager.get_current_file().get_basename()
        renamer = RenameDialog(self.window, basename, self.on_new_name_selected)
        renamer.show()

    def repeat_selection(self):
        if not self.last_target:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.undo_queue.append(self.file_manager.move_current(self.last_target))

    def undo_last(self):
        if not self.undo_queue:
            InfoDialog(self.window, "Nothing to undo!").run()
            return

        undo_action = self.undo_queue.pop()
        undo_action()

    def delete_image(self):
        basename = self.file_manager.get_current_file().get_basename()

        if QuestionDialog(self.window, "Send '%s' to the trash?" % basename).run():
            self.file_manager.delete_current()

    def zoom_in(self):
        self.image_viewer.adjust_zoom(+0.1)
        self.refresh_info()

    def zoom_out(self):
        self.image_viewer.adjust_zoom(-0.1)
        self.refresh_info()
    ##

    def run(self):
        gtk.main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('files', help='Files to organize', metavar='FILE', nargs='+')
    parser.add_argument('target', help='Target directory', metavar='TARGET')

    args = parser.parse_args()

    app = ViewerApp(args.files, args.target)
    app.run()

