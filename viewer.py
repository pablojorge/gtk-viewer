#!/usr/bin/env python

import os
import sys
import string

import pygtk
pygtk.require('2.0')
import gtk
import gio

import shutil

from monitor_proc import get_process_memory_usage

# XXX arreglar toma de parametros
# XXX hacer un cache limitado en lugar de cachear todo
# XXX mejorar creacion de widgets (emprolijar)
# XXX color de fondo (black background)

# XXX zoom para los animated gifs
# XXX hacer zoom in y out con mouse manteniendo el centro
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

class Size:
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
        return Size(size)

    def rename(self, new_name):
        shutil.move(self.filename, new_name)
        self.filename = new_name

    def safe_move(self, target):
        candidate = os.path.split(self.filename)[-1]

        index = 0
        while os.path.isfile(os.path.join(target, candidate)):
            name = os.path.split(''.join(self.filename.split('.')[:-1]))[-1]
            ext = self.filename.split('.')[-1]
            index += 1
            candidate = "%s (%d).%s" % (name, index, ext)

        final = os.path.join(target, candidate)
        self.rename(final)

    def trash(self):
        gfile = gio.File(path=self.filename)
        gfile.trash()

class ImageFile(File):
    def __init__(self, filename):
        File.__init__(self, filename)
        self.dimensions = None
        self.pixbuf_anim = None

    def get_pixbuf_anim(self):
        if not self.pixbuf_anim:
            self.pixbuf_anim = gtk.gdk.PixbufAnimation(self.get_filename())
        return self.pixbuf_anim

    def get_pixbuf_anim_at_size(self, width, height):
        raise NotImplemented()

    def get_pixbuf(self):
        return self.get_pixbuf_anim().get_static_image()

    def get_pixbuf_at_size(self, width, height):
        return self.get_pixbuf().scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)

    def is_static_image(self):
        return self.get_pixbuf_anim().is_static_image()

    def get_dimensions(self):
        if not self.dimensions:
            self.dimensions = ImageDimensions(self.get_pixbuf().get_width(), 
                                              self.get_pixbuf().get_height())
        return self.dimensions

class FileManager:
    def __init__(self, filelist, on_list_empty, on_list_modified):
        self.filelist = map(ImageFile, filelist)
        self.index = 0

        self.on_list_empty = on_list_empty
        self.on_list_modified = on_list_modified

    def get_current_file(self):
        return self.filelist[self.index]

    def get_prev_file(self):
        return self.filelist[self.index - 1]

    def get_next_file(self):
        return self.filelist[(self.index + 1) % len(self.filelist)]

    def get_current_index(self):
        return self.index

    def get_list_length(self):
        return len(self.filelist)

    def go_first(self):
        self.index = 0
        self.on_list_modified()

    def go_last(self):
        self.index = len(self.filelist) - 1
        self.on_list_modified()

    def go_forward(self, steps):
        self.index += steps
        if self.index >= len(self.filelist):
            self.index = self.index - len(self.filelist)
        self.on_list_modified()

    def go_backward(self, steps):
        self.index -= steps
        if self.index < 0:
            self.index = len(self.filelist) + self.index
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
        self.create_path(target)
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
        self.get_current_file().trash()
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

    def create_path(self, directory):
        stack = []

        while not os.path.isdir(directory):
            directory, basename = os.path.split(directory)
            stack.append(basename)

        while stack:
            basename = stack.pop()
            directory = os.path.join(directory, basename)
            os.mkdir(directory)

class SelectorDialog:
    def __init__(self, parent, initial_text, target_dir, last_targets, callback):
        self.target_dir = target_dir
        self.callback = callback

        self.window = gtk.Dialog(title="Selector", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("Specify target directory:")
        self.window.vbox.pack_start(label, True, True, 5)

        self.target_entry = gtk.Entry()
        self.target_entry.insert_text(initial_text)
        self.target_entry.connect("activate", self.on_entry_activate)
        completion = gtk.EntryCompletion()
        liststore = gtk.ListStore(str)
        for directory in sorted(self.__get_options()):
            liststore.append([directory.replace(target_dir, '')])
        completion.set_model(liststore)
        self.target_entry.set_completion(completion)
        completion.set_text_column(0)
        self.window.vbox.pack_start(self.target_entry, True, True, 5)

        label = gtk.Label()
        label.set_text("Choose previously used target:")
        self.window.vbox.pack_start(label, True, True, 5)

        combo = gtk.Combo()
        combo.entry.connect("activate", self.on_entry_activate)
        combo.entry.set_editable(False)
        combo.set_popdown_strings([target.replace(target_dir, '') for target in last_targets])
        combo.set_use_arrows(True)
        self.window.vbox.pack_start(combo, True, True, 5)

    def on_entry_activate(self, entry):
        target = os.path.join(self.target_dir, entry.get_text())
        gtk.Widget.destroy(self.window)
        self.callback(target)

    def __get_options(self):
        for root, dirs, files in os.walk(self.target_dir):
            if root != self.target_dir:
                yield root

    def show(self):
        self.window.show_all()
        self.target_entry.select_region(0,0)
        self.target_entry.set_position(self.target_entry.get_text_length())

class RenameDialog:
    def __init__(self, parent, basename, callback):
        self.basename = basename
        self.callback = callback

        self.window = gtk.Dialog(title="Rename", parent=parent, flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("New name:")
        self.window.action_area.pack_start(label, True, True, 5)

        self.entry = gtk.Entry()
        self.entry.connect("activate", self.on_entry_activate)
        self.entry.set_text(basename)

        self.window.action_area.pack_start(self.entry, True, True, 5)

    def on_entry_activate(self, entry):
        if entry.get_text() != self.basename:
            self.callback(entry.get_text())
        gtk.Widget.destroy(self.window)

    def show(self):
        self.window.show_all()
        self.entry.select_region(0, self.entry.get_text().rindex('.'))

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
        self.zoom_factor = 100
        self.image_file = None

    def get_widget(self):
        return self.widget

    def get_zoom_factor(self):
        return self.zoom_factor

    def set_zoom_factor(self, zoom_factor):
        if zoom_factor > 1:
            self.zoom_factor = zoom_factor

    def load(self, image_file):
        self.image_file = image_file
        self.set_zoom_factor(100)
        self.redraw()

    def load_at_size(self, image_file, width, height):
        self.image_file = image_file
        self.widget.set_size_request(width, height)
        self.force_zoom(width, height)
        self.redraw()

    def zoom_at_size(self, width, height):
        self.force_zoom(width, height)
        self.redraw()

    def zoom_at(self, zoom_factor):
        self.set_zoom_factor(zoom_factor)
        self.redraw()

    def redraw(self):
        dimensions = self.image_file.get_dimensions()

        width = int((dimensions.get_width() * self.zoom_factor) / 100)
        height = int((dimensions.get_height() * self.zoom_factor) / 100)

        if self.image_file.is_static_image():
            self.widget.set_from_pixbuf(self.image_file.get_pixbuf_at_size(width, height))
        else:
            self.widget.set_from_animation(self.image_file.get_pixbuf_anim())

    def force_zoom(self, width, height):
        im_dim = self.image_file.get_dimensions()
        zw = (float(width) / im_dim.get_width()) * 100
        zh = (float(height) / im_dim.get_height()) * 100
        self.set_zoom_factor(min(zw, zh))

class ViewerApp:
    DEF_WIDTH = 640
    DEF_HEIGHT = 480
    TH_SIZE = 200

    def __init__(self, filelist, target_dir):
        self.file_manager = FileManager(filelist,
                                        self.on_list_empty,
                                        self.on_list_modified)
        self.target_dir = target_dir

        self.last_targets = []
        self.undo_queue = []
        self.fullscreen = False

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_border_width(5)
        self.window.set_default_size(self.DEF_WIDTH, self.DEF_HEIGHT)
        self.window.connect("destroy", self.on_destroy)
        self.window.connect("key_press_event", self.on_key_press_event)
        self.window.set_position(gtk.WIN_POS_CENTER)

        vbox = gtk.VBox(False, 5)
        self.window.add(vbox)
        vbox.show()

        hbox = gtk.HBox(False, 5)
        vbox.pack_start(hbox, True, True, 0)
        hbox.show()

        go_back = gtk.Image()
        go_back.set_from_stock(gtk.STOCK_GO_BACK, 1)
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", self.on_th_prev_press)
        ebox.connect("scroll-event", self.on_th_scroll)
        ebox.add(go_back)
        ebox.show()
        hbox.pack_start(ebox, False, False, 0)
        go_back.show()

        self.th_left = ImageViewer()
        widget = self.th_left.get_widget()
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", self.on_th_prev_press)
        ebox.connect("scroll-event", self.on_th_scroll)
        ebox.add(widget)
        ebox.show()
        hbox.pack_start(ebox, False, False, 0)
        widget.show()

        self.scrolled = gtk.ScrolledWindow()
        self.scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.connect("scroll-event", self.on_viewer_scroll)
        self.scrolled_size = None
        self.scrolled.connect("size-allocate", self.on_viewer_size_allocate)
        hbox.pack_start(self.scrolled, True, True, 0)
        self.scrolled.show()
        #color = gtk.gdk.color_parse("#000000")
        #self.window.modify_bg(gtk.STATE_NORMAL, color)
        self.image_viewer = ImageViewer() 
        widget = self.image_viewer.get_widget()
        self.scrolled.add_with_viewport(widget)
        widget.show()

        self.th_right = ImageViewer()
        widget = self.th_right.get_widget()
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", self.on_th_next_press)
        ebox.connect("scroll-event", self.on_th_scroll)
        ebox.add(widget)
        ebox.show()
        hbox.pack_start(ebox, False, False, 0)
        widget.show()

        go_forward = gtk.Image()
        go_forward.set_from_stock(gtk.STOCK_GO_FORWARD, 1)
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", self.on_th_next_press)
        ebox.connect("scroll-event", self.on_th_scroll)
        ebox.add(go_forward)
        ebox.show()
        hbox.pack_start(ebox, False, False, 0)
        go_forward.show()

        self.status_bar = gtk.HBox(False, 5)
        vbox.pack_start(self.status_bar, False, False, 0)
        self.file_info = gtk.Label()
        self.file_info.show()
        self.status_bar.pack_start(self.file_info, False, False, 0)
        self.additional_info = gtk.Label()
        self.additional_info.show()
        self.status_bar.pack_start(self.additional_info, False, False, 0)
        self.file_index = gtk.Label()
        self.file_index.show()
        self.status_bar.pack_end(self.file_index, False, False, 0)
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
        elif key_name in string.letters:
            self.show_selector(key_name)        

    def on_viewer_size_allocate(self, widget, event, data=None):
        self.fit_viewer()
        self.refresh_info()

    def on_th_prev_press(self, widget, event, data=None):
        self.prev_image()

    def on_th_next_press(self, widget, event, data=None):
        self.next_image()

    def on_th_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            self.prev_image()
        else:
            self.next_image()

    def on_viewer_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            factor = 1.05
        else:
            factor = 0.95

        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * factor)
        self.refresh_info()
        return True # to prevent further processing
    ##

    ## Internal callbacks
    def on_target_selected(self, target):
        current = self.file_manager.get_current_file()

        if (not os.path.isdir(target) and 
            not QuestionDialog(self.window, 
                               "Create directory %s and move %s there?" % \
                               (target, current.get_basename())).run()):
            return

        if target in self.last_targets:
            self.last_targets.remove(target)

        self.last_targets.insert(0, target)

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
        self.fit_viewer(force=True)
        self.th_left.load_at_size(self.file_manager.get_prev_file(), self.TH_SIZE, self.TH_SIZE)
        self.th_right.load_at_size(self.file_manager.get_next_file(), self.TH_SIZE, self.TH_SIZE)
        self.refresh_info()

    def fit_viewer(self, force=False):
        allocation = self.scrolled.allocation
        width, height = allocation.width, allocation.height
        # Only redraw if size changed:
        if (width, height) != self.scrolled_size or force:
            self.image_viewer.zoom_at_size(width, height)
            self.scrolled_size = (width, height)

    def refresh_info(self):
        self.refresh_title()
        self.refresh_status()

    def refresh_title(self):
        image_file = self.file_manager.get_current_file()
        self.window.set_title(image_file.get_basename())

    def refresh_status(self):
        image_file = self.file_manager.get_current_file()

        file_info = "%s pixels  %s  %d%%" % (image_file.get_dimensions(),
                                             image_file.get_filesize(), 
                                             self.image_viewer.get_zoom_factor())
        file_index = "%d/%d" % (self.file_manager.get_current_index() + 1, 
                                self.file_manager.get_list_length())

        rss, vsize = get_process_memory_usage()
        additional_info = "RSS: %s VSize: %s" % (Size(rss), Size(vsize))

        if self.last_targets:
            last = self.last_targets[0].replace(self.target_dir, '')
            additional_info += " (press '.' to repeat '%s')" % last

        self.file_info.set_text(file_info)
        self.additional_info.set_text(additional_info)
        self.file_index.set_text(file_index)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        return {
            ## Generic actions:
            "Escape"      : self.quit_app,
            "F1"          : self.show_help,
            "F11"         : self.toggle_fullscreen,

            ## Files navigation:
            "Home"        : self.first_image,
            "End"         : self.last_image,
            "Page_Down"   : self.jump_forward,
            "Page_Up"     : self.jump_backward,
            "space"       : self.next_image,
            "Right"       : self.next_image,
            "Return"      : self.next_image,
            "BackSpace"   : self.prev_image,
            "Left"        : self.prev_image,

            ## Files manipulation:
            "Down"        : self.show_selector,
            "Tab"         : self.show_selector,
            "F2"          : self.rename_current,
            "period"      : self.repeat_selection,
            "comma"       : self.undo_last,
            "Delete"      : self.delete_image,

            ## Zoom:
            "1"           : self.zoom_100,
            "0"           : self.zoom_fit,
            "KP_Add"      : self.zoom_in,
            "plus"        : self.zoom_in,
            "KP_Subtract" : self.zoom_out,
            "minus"       : self.zoom_out,
        }

    ## action handlers
    def quit_app(self):
        gtk.Widget.destroy(self.window)

    def show_help(self):
        helpd = HelpDialog(self.window, self.get_key_bindings())
        helpd.show()

    def toggle_fullscreen(self):
        if not self.fullscreen:
            self.window.fullscreen()
            self.fullscreen = True
        else:
            self.window.unfullscreen()
            self.fullscreen = False

    def first_image(self):
        self.file_manager.go_first()

    def last_image(self):
        self.file_manager.go_last()

    def jump_forward(self):
        self.file_manager.go_forward(10)

    def jump_backward(self):
        self.file_manager.go_backward(10)

    def next_image(self):
        self.file_manager.go_forward(1)

    def prev_image(self):
        self.file_manager.go_backward(1)

    def show_selector(self, initial_text=''):
        selector = SelectorDialog(self.window,
                                  initial_text, 
                                  self.target_dir, 
                                  self.last_targets, 
                                  self.on_target_selected)
        selector.show()

    def rename_current(self):
        basename = self.file_manager.get_current_file().get_basename()
        renamer = RenameDialog(self.window, basename, self.on_new_name_selected)
        renamer.show()

    def repeat_selection(self):
        if not self.last_targets:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.undo_queue.append(self.file_manager.move_current(self.last_targets[0]))

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

    def zoom_100(self):
        self.image_viewer.zoom_at(100)
        self.refresh_info()

    def zoom_fit(self):
        self.fit_viewer(force=True)
        self.refresh_info()

    def zoom_in(self):
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 1.20)
        self.refresh_info()

    def zoom_out(self):
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 0.80)
        self.refresh_info()
    ##

    def run(self):
        gtk.main()

if __name__ == "__main__":
    files = sys.argv[1:]
    app = ViewerApp(files, None)
    app.run()

