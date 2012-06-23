#!/usr/bin/env python

import os
import sys
import string

import pygtk
pygtk.require('2.0')
import gtk
import gio

import hashlib
import time
import glob
import shutil
import optparse

# TODO:
#
#  Funcionalidad:
#
#  * rename dialog como un save dialog
#  * soporte para copiar ademas de mover
#  * hacer un menu y un toolbox
#  * apretar ESC en fullscreen saca de fullscreen (cambiar dinamicamente
#    los bindings, con un get que devuleve bindings de acuerdo al modo)
#  * hacer un help
#
#  Video:
#
#  * https://github.com/felipec/gst-player
#  * http://code.google.com/p/gst-player/
#  * http://mail.python.org/pipermail/python-es/2006-August/thread.html#13771
#  * http://gstreamer-devel.966125.n4.nabble.com/How-to-embed-video-in-gtk-app-td970597.html
#  * http://stackoverflow.com/questions/6078368/how-to-embed-video-in-gtk-application-window-using-gstreamer-xoverlay
#  * http://www.daa.com.au/pipermail/pygtk/2008-June/015332.html

class Cache:
    def __init__(self, limit=None):
        self.keys = []
        self.limit = limit
        self.store = {}
        self.hits = 0
        self.misses = 0

    def __add_key(self, key):
        if self.limit is None:
            return

        if len(self.keys) == self.limit:
            older = self.keys[0]
            del self.store[older]
            del self.keys[0]

        self.keys.append(key)

    def __refresh_key(self, key):
        if self.limit is None:
            return

        del self.keys[self.keys.index(key)]
        self.keys.append(key)

    def __setitem__(self, key, value):
        self.__add_key(key)
        self.store[key] = value

    def __getitem__(self, key):
        try:
            value = self.store[key]
            self.hits += 1
            self.__refresh_key(key)
            return value
        except:
            self.misses += 1
            raise

def cached(cache_=None):
    def func(method):
        def wrapper(self, *args, **kwargs):
            key = (hash(self),
                   method.__name__,
                   args,
                   tuple(kwargs.items()))

            if not cache_:
                if not hasattr(self, "__cache__"):
                    self.__cache__ = Cache()
                cache = self.__cache__
            else:
                cache = cache_
    
            try:
                return cache[key]
            except:
                value = method(self, *args, **kwargs)
                cache[key] = value
                return value
        return wrapper
    return func

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

    def __str__(self):
        if self.size < 1024:
            return "%d bytes" % self.size
        elif self.size < (1024*1024):
            return "%.2f Kb" % (self.size/1024)
        else:
            return "%.2f Mb" % (self.size/(1024*1024))

class Datetime:
    def __init__(self, datetime):
        self.datetime = datetime

    def __lt__(self, other):
        return self.datetime < other.datetime

    def __str__(self):
        return time.strftime("%a %b %d %Y %X", time.localtime(self.datetime))

class File:
    def __init__(self, filename):
        self.filename = filename

    def get_filename(self):
        return self.filename

    def get_dirname(self):
        return os.path.dirname(self.filename)

    def get_basename(self):
        return os.path.basename(self.filename)

    def get_filesize(self):
        stat = os.stat(self.filename)
        size = stat.st_size
        return Size(size)

    @cached()
    def get_sha1(self):
        with open(self.filename, "r") as input_:
            return hashlib.sha1(input_.read()).hexdigest()

    def get_atime(self):
        return Datetime(os.stat(self.filename).st_atime)

    def get_mtime(self):
        return Datetime(os.stat(self.filename).st_mtime)

    def get_ctime(self):
        return Datetime(os.stat(self.filename).st_ctime)

    def __hash__(self):
        return hash(self.filename)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.filename == other
        else:
            raise Exception("Can't compare File to " + repr(other))

    def rename(self, new_name):
        shutil.move(self.filename, new_name)
        self.filename = new_name

    def trash(self):
        gfile = gio.File(path=self.filename)
        gfile.trash()

    def untrash(self):
        # XXX linux-only
        trash_dir = os.getenv("HOME") + "/.local/share/Trash"
        info_dir = trash_dir + "/info"
        files_dir = trash_dir + "/files"
        
        info_files = glob.glob(info_dir + "/*")
        
        for info_file in info_files:
            with open(info_file, "r") as info:
                lines = info.readlines()
            for line in lines:
                if line.startswith("Path="):
                    path = line[line.index("=")+1:-1]
                    if path == os.path.abspath(self.filename):
                        trashed_file = info_file.replace(info_dir, files_dir)
                        trashed_file = trashed_file.replace(".trashinfo", "")
                        os.unlink(info_file)
                        shutil.move(trashed_file, self.filename)
                        return
        
        raise Exception("Couldn't find '%s' in trash" % self.filename)

class ImageFile(File):
    pixbuf_cache = Cache(10)
    pixbuf_anim_cache = Cache(10)

    def __init__(self, filename):
        File.__init__(self, filename)
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False

    @cached(pixbuf_cache)
    def get_pixbuf(self):
        return gtk.gdk.pixbuf_new_from_file(self.get_filename())

    def is_static_image(self):
        return ".gif" not in self.get_basename() # XXX

    @cached(pixbuf_anim_cache)
    def get_pixbuf_anim_at_size(self, width, height):
        loader = gtk.gdk.PixbufLoader()
        loader.set_size(width, height)
        with open(self.get_filename(), "r") as input_:
            loader.write(input_.read())
        loader.close()
        return loader.get_animation()

    def toggle_flip(self, horizontal):
        if horizontal:
            self.flip_h = not self.flip_h
        else:
            self.flip_v = not self.flip_v

    def rotate(self, clockwise):
        angle = (+90 if clockwise else -90)
        self.rotation = (self.rotation + angle) % 360

    def get_pixbuf_at_size(self, width, height):
        angle_constants = {0: gtk.gdk.PIXBUF_ROTATE_NONE,
                           90: gtk.gdk.PIXBUF_ROTATE_CLOCKWISE,
                           180: gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN,
                           270: gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE}
    
        pixbuf = self.get_pixbuf()
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        flipped = scaled.flip(True) if self.flip_h else scaled
        flipped = flipped.flip(False) if self.flip_v else flipped
        rotated = flipped.rotate_simple(angle_constants[self.rotation])

        return rotated

    @cached()
    def get_dimensions(self):
        return ImageDimensions(self.get_pixbuf().get_width(), 
                               self.get_pixbuf().get_height())

class Action:
    NORMAL = 0
    WARNING = 1
    DANGER = 2

    def __init__(self, severity, description, undo):
        self.severity = severity
        self.description = description
        self.undo = undo

class FileManager:
    def __init__(self, on_list_empty, on_list_modified):
        self.filelist = []
        self.index = 0

        self.on_list_empty = on_list_empty
        self.on_list_modified = on_list_modified

    def set_files(self, filelist):
        self.filelist = map(ImageFile, filelist)

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

    def empty(self):
        return not self.filelist

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

    def go_file(self, filename):
        self.index = self.filelist.index(filename)
        self.on_list_modified()

    def sort_by_date(self, reverse):
        filename = self.get_current_file().get_filename()
        self.filelist = sorted(self.filelist, 
                               key=lambda file_: file_.get_mtime(),
                               reverse=reverse)
        self.go_file(filename)

    def sort_by_name(self, reverse):
        filename = self.get_current_file().get_filename()
        self.filelist = sorted(self.filelist, 
                               key=lambda file_: file_.get_filename(),
                               reverse=reverse)
        self.go_file(filename)

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

        return Action(Action.NORMAL,
                      "'%s' renamed to '%s'" % (orig_name, current.get_basename()),
                      undo_action)

    def move_current(self, target_dir, target_name=''):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_filename = current.get_filename()

        if not target_name:
            target_name = current.get_basename()

        new_filename = os.path.join(target_dir, target_name)

        if os.path.isfile(new_filename):
            return self.handle_duplicate(target_dir, target_name)

        current.rename(new_filename)
        self.on_current_eliminated()

        def undo_action():
            restored = ImageFile(new_filename)
            restored.rename(orig_filename)
            self.filelist.insert(orig_index, restored)
            self.index = orig_index # XXX podria ser out of bounds
            self.on_list_modified()

        return Action(Action.NORMAL,
                      "'%s' moved to '%s'" % (orig_filename, target_dir),
                      undo_action)

    def delete_current(self):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_filename = current.get_filename()

        current.trash()
        self.on_current_eliminated()

        def undo_action():
            restored = ImageFile(orig_filename)
            restored.untrash()
            self.filelist.insert(orig_index, restored)
            self.index = orig_index # XXX podria ser out of bounds
            self.on_list_modified()

        return Action(Action.DANGER,
                      "'%s' deleted" % (orig_filename),
                      undo_action)

    def toggle_star(self):
        current = self.get_current_file()
        orig_index = self.get_current_index()
        orig_name = current.get_basename()
        name, sep, ext = orig_name.rpartition(".")
        star_marker = " (S)"
        was_starred = name.endswith(star_marker)
        new_name = name.replace(star_marker, "") if was_starred else name + star_marker
        current.rename(os.path.join(current.get_dirname(), string.join((new_name, ext), sep)))
        self.on_list_modified()

        def undo_action():
            current.rename(os.path.join(current.get_dirname(), orig_name))
            self.index = orig_index # XXX podria no existir mas
            self.on_list_modified()

        return Action(Action.NORMAL,
                      "'%s' %s" % (orig_name, "unstarred" if was_starred else "starred"),
                      undo_action)

    # Internal helpers:
    def get_safe_candidate(self, target):
        filename = self.get_current_file().get_filename()
        candidate = os.path.basename(filename)

        index = 0
        while os.path.isfile(os.path.join(target, candidate)):
            name = os.path.basename(''.join(filename.split('.')[:-1]))
            ext = filename.split('.')[-1]
            index += 1
            candidate = "%s (%d).%s" % (name, index, ext)

        return candidate

    def handle_duplicate(self, target_dir, target_name):
        current = self.get_current_file()
        orig_filename = current.get_filename()
        new_file = ImageFile(os.path.join(target_dir, target_name))

        if current.get_sha1() == new_file.get_sha1():
            action = self.delete_current()
            action.description = "'%s' deleted to avoid duplicates" % orig_filename
            return action
        else:
            candidate = self.get_safe_candidate(target_dir)
            action = self.move_current(target_dir, candidate)
            action.severity = Action.WARNING
            action.description = "'%s' auto-renamed to '%s' in '%s'" % (orig_filename, candidate, target_dir)
            return action

    def on_current_eliminated(self):
        del self.filelist[self.index]

        if not self.filelist:
            self.on_list_empty()
        else:
            if self.index >= len(self.filelist):
                self.index = self.index - len(self.filelist)
            self.on_list_modified()

class SelectorDialog:
    def __init__(self, initial_dir, last_targets, callback):
        self.callback = callback

        self.chooser = gtk.FileChooserDialog(title="Specify target directory",
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
            files = get_files_from_dir(dirname)
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

class OpenDialog:
    def __init__(self, initial_dir, callback):
        self.callback = callback

        self.chooser = gtk.FileChooserDialog(title="Open file",
                                             action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                             buttons=(gtk.STOCK_CANCEL, 
                                                      gtk.RESPONSE_CANCEL,
                                                      gtk.STOCK_OPEN,
                                                      gtk.RESPONSE_OK))

        if initial_dir:
            self.chooser.set_current_folder(initial_dir)

        self.th_viewer = ThumbnailViewer(300)
        widget = self.th_viewer.get_widget()

        self.chooser.set_preview_widget(widget)
        self.chooser.set_preview_widget_active(True)
        self.chooser.connect("selection-changed", self.on_selection_changed)

        img_filter = gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_pixbuf_formats()
        self.chooser.add_filter(img_filter)

    def on_selection_changed(self, chooser):
        filename = chooser.get_preview_filename()
        if filename:
            if os.path.isfile(filename):
                self.th_viewer.load(ImageFile(filename))
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

    def flip_horizontal(self):
        self.image_file.toggle_flip(True)
        self.redraw()

    def flip_vertical(self):
        self.image_file.toggle_flip(False)
        self.redraw()

    def rotate_c(self):
        self.image_file.rotate(clockwise=True)
        self.redraw()

    def rotate_cc(self):
        self.image_file.rotate(clockwise=False)
        self.redraw()

    def get_scaled_size(self):
        dimensions = self.image_file.get_dimensions()

        width = int((dimensions.get_width() * self.zoom_factor) / 100)
        height = int((dimensions.get_height() * self.zoom_factor) / 100)

        return width, height

    def redraw(self):
        width, height = self.get_scaled_size()

        if self.image_file.is_static_image():
            self.widget.set_from_pixbuf(self.image_file.get_pixbuf_at_size(width, height))
        else:
            self.widget.set_from_animation(self.image_file.get_pixbuf_anim_at_size(width, height))

    def force_zoom(self, width, height):
        im_dim = self.image_file.get_dimensions()
        zw = (float(width) / im_dim.get_width()) * 99
        zh = (float(height) / im_dim.get_height()) * 99
        self.set_zoom_factor(min(zw, zh))

class ThumbnailViewer(ImageViewer):
    def __init__(self, th_size):
        ImageViewer.__init__(self)
        self.th_size = th_size
        self.hidden = False

    def load(self, image_file):
        self.load_at_size(image_file, self.th_size, self.th_size)

    def redraw(self):
        if self.hidden:
            return

        dimensions = self.image_file.get_dimensions()

        width = int((dimensions.get_width() * self.zoom_factor) / 100)
        height = int((dimensions.get_height() * self.zoom_factor) / 100)

        self.widget.set_from_pixbuf(self.image_file.get_pixbuf_at_size(width, height))

    def hide(self):
        self.hidden = True
        self.widget.hide()

    def show(self):
        self.hidden = False
        self.widget.show()
        self.redraw()

    def toggle_visible(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

class AutoScrolledWindow:
    def __init__(self, child, bg_color, on_special_drag_left, 
                                        on_special_drag_right, 
                                        on_scroll_event, 
                                        on_size_allocate):
        self.scrolled = gtk.ScrolledWindow()
        self.scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled.connect("size-allocate", on_size_allocate)

        self.scrolled.add_with_viewport(child)
        viewport = child.get_parent()

        self.on_special_drag_left = on_special_drag_left
        self.on_special_drag_right = on_special_drag_right

        viewport.connect("scroll-event", self.on_scroll_event, on_scroll_event)
        viewport.connect("button-press-event", self.on_button_press_event)
        viewport.connect("button-release-event", self.on_button_release_event)
        viewport.connect("motion-notify-event", self.on_motion_notify_event)

        viewport.set_events(gtk.gdk.EXPOSURE_MASK | 
                            gtk.gdk.LEAVE_NOTIFY_MASK | 
                            gtk.gdk.BUTTON_PRESS_MASK | 
                            gtk.gdk.BUTTON_RELEASE_MASK | 
                            gtk.gdk.POINTER_MOTION_MASK | 
                            gtk.gdk.POINTER_MOTION_HINT_MASK)

        viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(bg_color))

    def get_widget(self):
        return self.scrolled

    def on_button_press_event(self, widget, event):
        if event.button == 1: # left
            widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

        self.prev_x = event.x_root
        self.prev_y = event.y_root

    def on_button_release_event(self, widget, event):
        if event.button == 1:
            widget.window.set_cursor(None)
        elif event.button == 3:
            offset = self.prev_x - event.x_root
            if offset < 0:
                self.on_special_drag_left()
            elif offset >= 0:
                self.on_special_drag_right()

    def on_motion_notify_event(self, widget, event):
        if not event.state & gtk.gdk.BUTTON1_MASK:
            return

        offset_x = self.prev_x - event.x_root
        offset_y = self.prev_y - event.y_root

        self.prev_x = event.x_root
        self.prev_y = event.y_root

        x_adj = widget.get_hadjustment()
        y_adj = widget.get_vadjustment() 

        new_x = x_adj.get_value() + offset_x
        new_y = y_adj.get_value() + offset_y

        if (new_x >= x_adj.get_lower() and 
            new_x <= (x_adj.get_upper() - x_adj.get_page_size())):
            x_adj.set_value(new_x)

        if (new_y >= y_adj.get_lower() and 
            new_y <= (y_adj.get_upper() - y_adj.get_page_size())):
            y_adj.set_value(new_y)

    def on_scroll_event(self, widget, event, callback):
        # to prevent partial re-drawings:
        widget.get_window().freeze_updates()

        # get full img size before and after zoom:
        old_size, new_size = callback(widget, event)

        # calculate the offset off the pointer inside the viewport:
        win_root = widget.get_window().get_origin()
        event_root = event.get_root_coords()

        event_x = event_root[0] - win_root[0]
        event_y = event_root[1] - win_root[1]

        # calculate the proportional location of the pointer inside the img:
        x_adj = widget.get_hadjustment()
        y_adj = widget.get_vadjustment() 

        px = (x_adj.get_value() + event_x) / old_size[0]
        py = (y_adj.get_value() + event_y) / old_size[1]

        # adjust the scrollbars to maintain the same position of the cursor:
        new_x = px * new_size[0] - event_x
        new_y = py * new_size[1] - event_y

        x_adj.set_value(new_x)
        y_adj.set_value(new_y)

        # re-enable updates:
        widget.get_window().thaw_updates()

        return True # to prevent further processing

class WidgetFactory:
    def __init__(self):
        pass

    def get_window(self, width, height, on_destroy, on_key_press_event):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_default_size(width, height)
        window.connect("destroy", on_destroy)
        window.connect("key_press_event", on_key_press_event)
        window.set_position(gtk.WIN_POS_CENTER)
        return window

    def get_image_from_stock(self, stock_id, size):
        image = gtk.Image()
        image.set_from_stock(stock_id, size)
        return image

    def get_event_box(self, child, bg_color, on_button_press_event, on_scroll_event):
        ebox = gtk.EventBox()
        ebox.connect("button-press-event", on_button_press_event)
        ebox.connect("scroll-event", on_scroll_event)
        ebox.add(child)
        ebox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(bg_color))
        return ebox

class ViewerApp:
    DEF_WIDTH = 640
    DEF_HEIGHT = 480
    TH_SIZE = 200
    BG_COLOR = "#000000"

    def __init__(self, files, start_file, base_dir=None):
        ### Data definition
        self.file_manager = FileManager(self.on_list_empty,
                                        self.on_list_modified)

        self.files_order = None
        self.base_dir = base_dir
        self.last_opened_file = None
        self.last_targets = []
        self.undo_stack = []

        self.fullscreen = False

        ### Window composition
        factory = WidgetFactory()

        self.window = factory.get_window(width=self.DEF_WIDTH, 
                                         height=self.DEF_HEIGHT,
                                         on_destroy=self.on_destroy,
                                         on_key_press_event=self.on_key_press_event)

        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, True, True, 0)

        # Left thumbnail
        go_back = factory.get_image_from_stock(gtk.STOCK_GO_BACK, 1)
        ebox = factory.get_event_box(child=go_back,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_prev_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        self.th_left = ThumbnailViewer(self.TH_SIZE)
        ebox = factory.get_event_box(child=self.th_left.get_widget(),
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_prev_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Main viewer
        self.image_viewer = ImageViewer() 
        self.scrolled_size = None
        self.scrolled = AutoScrolledWindow(child=self.image_viewer.get_widget(),
                                           bg_color=self.BG_COLOR,
                                           on_special_drag_left=self.on_viewer_drag_left,
                                           on_special_drag_right=self.on_viewer_drag_right,
                                           on_scroll_event=self.on_viewer_scroll,
                                           on_size_allocate=self.on_viewer_size_allocate)
        hbox.pack_start(self.scrolled.get_widget(), True, True, 0)

        # Right thumbnail
        self.th_right = ThumbnailViewer(self.TH_SIZE)
        ebox = factory.get_event_box(child=self.th_right.get_widget(),
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        go_forward = factory.get_image_from_stock(gtk.STOCK_GO_FORWARD, 1)
        ebox = factory.get_event_box(child=go_forward,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Status Bar:
        self.status_bar = gtk.HBox(False, 0)
        vbox.pack_start(self.status_bar, False, False, 5)

        self.file_info = gtk.Label()
        self.memory_info = gtk.Label()
        self.additional_info = gtk.Label()
        self.file_index = gtk.Label()

        self.status_bar.pack_start(self.file_info, False, False, 10)
        self.status_bar.pack_start(self.memory_info, False, False, 10)
        self.status_bar.pack_start(self.additional_info, False, False, 10)

        self.status_bar.pack_end(self.file_index, False, False, 10)

        if files:
            self.set_files(files, start_file)
        else:
            open_dialog = OpenDialog(initial_dir=".", 
                                     callback=self.on_file_selected)
            open_dialog.run()

            if self.file_manager.empty():
                raise Exception("No files selected!")

        self.window.show_all()

    def set_files(self, files, start_file):
        self.file_manager.set_files(files)

        self.files_order = None
        self.undo_stack = []

        if start_file:
            self.file_manager.go_file(start_file)

        self.reload_viewer()

    ## Gtk event handlers
    def on_destroy(self, widget):
        gtk.main_quit()

    def on_key_press_event(self, widget, event, data=None):
        key_name = gtk.gdk.keyval_name(event.keyval)
        #print "key pressed:", key_name

        bindings = self.get_key_bindings()

        if key_name in bindings:
            bindings[key_name]()

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

    # not real gtk events:
    def on_viewer_drag_left(self): self.prev_image()
    def on_viewer_drag_right(self): self.next_image()

    def on_viewer_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            factor = 1.05
        else:
            factor = 0.95

        old_size = self.image_viewer.get_scaled_size()

        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * factor)
        self.refresh_info()

        new_size = self.image_viewer.get_scaled_size()

        return old_size, new_size
    ##

    ## Internal callbacks
    def on_target_selected(self, target):
        self.move_current(target)

    def on_base_dir_selected(self, base_dir):
        self.base_dir = base_dir
        self.refresh_info()

    def on_file_selected(self, filename):
        self.last_opened_file = filename
        files, start_file = get_files_from_args([filename])
        self.set_files(files, start_file)

    def on_new_name_selected(self, new_name):
        if os.path.isfile(new_name):
            InfoDialog(self.window, "'%s' already exists!" % new_name).run()
            return

        self.undo_stack.append(self.file_manager.rename_current(new_name))

    def on_list_empty(self):
        if QuestionDialog(self.window, "No more files, select new one?").run():
            initial_dir = None
            if self.last_opened_file:
                initial_dir = os.path.dirname(self.last_opened_file)
            open_dialog = OpenDialog(initial_dir=initial_dir, 
                                     callback=self.on_file_selected)
            open_dialog.run()
        else:
            InfoDialog(self.window, "No more files, exiting").run()
            self.quit_app()

    def on_list_modified(self):
        self.reload_viewer()
    ## 

    ## Internal helpers
    def move_current(self, target_dir):
        if target_dir in self.last_targets:
            self.last_targets.remove(target_dir)

        self.last_targets.insert(0, target_dir)

        self.undo_stack.append(self.file_manager.move_current(target_dir))

    def reload_viewer(self):
        self.image_viewer.load(self.file_manager.get_current_file())
        self.th_left.load(self.file_manager.get_prev_file())
        self.th_right.load(self.file_manager.get_next_file())

        self.fit_viewer(force=True)
        self.refresh_info()

    def fit_viewer(self, force=False):
        allocation = self.scrolled.get_widget().allocation
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
        self.window.set_title(image_file.get_filename())

    def refresh_status(self):
        image_file = self.file_manager.get_current_file()

        # Markup reference:
        # http://www.gtk.org/api/2.6/pango/PangoMarkupFormat.html

        self.file_info.set_markup("<i>Date:</i> %s\n<i>Size:</i> %s pixels | %s | %d%%\n<i>SHA1:</i> %s" % \
                                  (image_file.get_mtime(),
                                   image_file.get_dimensions(),
                                   image_file.get_filesize(), 
                                   self.image_viewer.get_zoom_factor(),
                                   image_file.get_sha1()))

        rss, vsize = get_process_memory_usage()
        self.memory_info.set_markup("<i>RSS:</i> %s\n<i>VSize:</i> %s" % (Size(rss), Size(vsize)))

        additional = "<i>Base directory:</i> <b>%s</b>" % self.base_dir

        if self.last_targets:
            additional += "\n<i>Last directory:</i> <b>%s</b>" % self.last_targets[0]

        if self.undo_stack:
            last_action = self.undo_stack[-1]
            background, foreground = {
                Action.NORMAL : ("green", None),
                Action.WARNING : ("yellow", None),
                Action.DANGER : ("red", "white")
            }[last_action.severity]
            span = "<span"
            if background: span += " background='%s'" % background
            if foreground: span += " foreground='%s'" % foreground
            span += ">%s</span>" % last_action.description
            additional += "\n<i>Last action:</i> " + span

        self.additional_info.set_markup("%s" % additional)

        self.file_index.set_markup("<b><big>%d/%d</big></b>\n<i>Order:</i> %s" % \
                                   (self.file_manager.get_current_index() + 1, 
                                    self.file_manager.get_list_length(),
                                    self.files_order))
        self.file_index.set_justify(gtk.JUSTIFY_RIGHT)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        return {
            ## Generic actions:
            "q"           : self.quit_app,
            "Escape"      : self.quit_app,
            "F1"          : self.show_help,
            "F11"         : self.toggle_fullscreen,
            "F12"         : self.toggle_thumbnails,

            ## Files navigation:
            "Home"        : self.first_image,
            "End"         : self.last_image,
            "Page_Down"   : self.jump_forward,
            "Page_Up"     : self.jump_backward,
            "space"       : self.next_image,
            "Right"       : self.next_image,
            "BackSpace"   : self.prev_image,
            "Left"        : self.prev_image,

            ## Files manipulation:
            "Down"        : self.show_selector,
            "Tab"         : self.show_selector,
            "o"           : self.open_file,
            "F2"          : self.rename_current,
            "F3"          : self.select_base_dir,
            "period"      : self.repeat_selection,
            "Return"      : self.repeat_selection,
            "z"           : self.undo_last,
            "s"           : self.toggle_star,
            "Delete"      : self.delete_image,
            "d"           : self.sort_by_date_asc,
            "D"           : self.sort_by_date_desc,
            "n"           : self.sort_by_name_asc,
            "N"           : self.sort_by_name_desc,

            ## Image manipulation:
            "1"           : self.zoom_100,
            "0"           : self.zoom_fit,
            "r"           : self.rotate_c,
            "R"           : self.rotate_cc,
            "f"           : self.flip_horizontal,
            "F"           : self.flip_vertical,
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
            self.status_bar.hide()
            self.fullscreen = True
        else:
            self.window.unfullscreen()
            self.status_bar.show()
            self.fullscreen = False

    def toggle_thumbnails(self):
        self.th_left.toggle_visible()
        self.th_right.toggle_visible()

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

    def show_selector(self):
        if self.base_dir:
            initial_dir = self.base_dir
        else:
            initial_dir = self.file_manager.get_current_file().get_dirname()

        selector = SelectorDialog(initial_dir=initial_dir, 
                                  last_targets=self.last_targets, 
                                  callback=self.on_target_selected)
        selector.run()

    def open_file(self):
        initial_dir = self.file_manager.get_current_file().get_dirname()
        open_dialog = OpenDialog(initial_dir, self.on_file_selected)
        open_dialog.run()

    def rename_current(self):
        basename = self.file_manager.get_current_file().get_basename()
        renamer = RenameDialog(self.window, basename, self.on_new_name_selected)
        renamer.show()

    def select_base_dir(self):
        if self.base_dir:
            initial_dir = self.base_dir
        else:
            initial_dir = self.file_manager.get_current_file().get_dirname()
        selector = SelectorDialog(initial_dir=initial_dir, 
                                  last_targets=[], 
                                  callback=self.on_base_dir_selected)
        selector.run()

    def repeat_selection(self):
        if not self.last_targets:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.move_current(self.last_targets[0])

    def undo_last(self):
        if not self.undo_stack:
            InfoDialog(self.window, "Nothing to undo!").run()
            return

        action = self.undo_stack.pop()
        action.undo()

    def toggle_star(self):
        self.undo_stack.append(self.file_manager.toggle_star())

    def delete_image(self):
        self.undo_stack.append(self.file_manager.delete_current())

    def sort_by_date_asc(self):
        self.files_order = "Date Asc"
        self.file_manager.sort_by_date(reverse=False)

    def sort_by_date_desc(self):
        self.files_order = "Date Desc"
        self.file_manager.sort_by_date(reverse=True)

    def sort_by_name_asc(self):
        self.files_order = "Name Asc"
        self.file_manager.sort_by_name(reverse=False)

    def sort_by_name_desc(self):
        self.files_order = "Name Desc"
        self.file_manager.sort_by_name(reverse=True)

    def zoom_100(self):
        self.image_viewer.zoom_at(100)
        self.refresh_info()

    def zoom_fit(self):
        self.fit_viewer(force=True)
        self.refresh_info()

    def rotate_c(self):
        self.image_viewer.rotate_c()

    def rotate_cc(self):
        self.image_viewer.rotate_cc()

    def flip_horizontal(self):
        self.image_viewer.flip_horizontal()

    def flip_vertical(self):
        self.image_viewer.flip_vertical()

    ##

    def run(self):
        gtk.main()

def has_known_file_ext(filename):
    for format_ in gtk.gdk.pixbuf_get_formats():
        for extension in format_["extensions"]:
            if ("." + extension) in filename.lower():
                return True

    return False

def get_files_from_dir(directory):
    files = []

    for filename in glob.glob(os.path.join(directory, "*")):
        if has_known_file_ext(filename):
            files.append(filename)

    return sorted(files)

def get_files_from_args(args):
    files = []
    start_file = None

    if len(args) == 1: 
        if os.path.isdir(args[0]):
            files = get_files_from_dir(args[0])
        else:
            if has_known_file_ext(args[0]):
                start_file = args[0]
            files = get_files_from_dir(os.path.dirname(args[0]))
    else:
        for arg in args:
            if os.path.isdir(arg):
                files.extend(get_files_from_dir(arg))
            elif has_known_file_ext(arg):
                files.append(arg)

    return files, start_file

def get_process_memory_usage(pid=os.getpid(), pagesize=4096):
    # XXX linux-only
    with open("/proc/%i/stat" % pid) as statfile:
        stat = statfile.read().split(' ')

        rss = int(stat[23]) * pagesize
        vsize = int(stat[22])

        return (rss, vsize)

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] FILE...")

    parser.add_option("", "--base-dir")

    options, args = parser.parse_args()

    files, start_file = get_files_from_args(args)

    try:
        app = ViewerApp(files, start_file, options.base_dir)
        app.run()
    except Exception, e:
        print "Error:", e

if __name__ == "__main__":
    main()
