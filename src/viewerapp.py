import os
import signal

import gtk

from filefactory import FileFactory

from imagefile import Size
from filemanager import Action, FileManager
from dialogs import (OpenDialog, InfoDialog, QuestionDialog, AboutDialog,
                     FileSelectorDialog, BasedirSelectorDialog, TargetSelectorDialog, 
                     RenameDialog)
from imageviewer import ImageViewer, ThumbnailViewer

from filescanner import get_files_from_args
from utils import get_process_memory_usage

class BlockedWidget:
    def __init__(self, widget, handler_id):
        self.widget = widget
        self.handler_id = handler_id

    def __enter__(self):
        self.widget.handler_block(self.handler_id)
        return self.widget

    def __exit__(self, *tb_info):
        self.widget.handler_unblock(self.handler_id)

class WidgetManager:
    def __init__(self):
        self.widget_dict = {}

    def add_widget(self, key, widget, handler_id):
        self.widget_dict[key] = widget
        self.widget_dict[key + "_handler"] = handler_id

    def get(self, key):
        return self.widget_dict[key]

    def get_blocked(self, key):
        return BlockedWidget(self.widget_dict[key],
                             self.widget_dict[key + "_handler"])

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

        if bg_color:
            color = gtk.gdk.color_parse(bg_color)
            ebox.modify_bg(gtk.STATE_NORMAL, color)

        return ebox

    def get_menu(self, menu, widget_manager, accel_group):
        gmenu = gtk.Menu()
        gitem = gtk.MenuItem(menu["text"])
        gitem.set_submenu(gmenu)

        for item in menu["items"]:
            # Create menu item depending on type:
            if item.has_key("menu"):
                mitem = self.get_menu(item["menu"], widget_manager, accel_group)
            elif item.has_key("text"):
                mitem = gtk.MenuItem(item["text"])
            elif item.has_key("stock"):
                mitem = gtk.ImageMenuItem(item["stock"], accel_group)
            elif item.has_key("separator"):
                mitem = gtk.SeparatorMenuItem()
            elif item.has_key("toggle"):
                mitem = gtk.CheckMenuItem(item["toggle"])
                if item.has_key("active") and item["active"]:
                    mitem.set_active(True)

            if item.has_key("accel"):
                accel = item["accel"]
                if type(accel) is str:
                    key, mod = gtk.accelerator_parse(item["accel"])
                else:
                    key, mod = accel
                mitem.add_accelerator("activate", accel_group, key, mod, gtk.ACCEL_VISIBLE)

            if item.has_key("sensitive"):
                mitem.set_sensitive(item["sensitive"])

            # Connect handler if available:
            if item.has_key("handler"):
                handler_id = mitem.connect("activate", item["handler"])
            else:
                handler_id = None

            if item.has_key("key"):
                widget_manager.add_widget(item["key"], mitem, handler_id)

            # Add it to the menu:
            gmenu.append(mitem)
        
        return gitem

    def get_menu_bar(self, window, widget_manager, menus):
        menu_bar = gtk.MenuBar()

        accel_group = gtk.AccelGroup()
        window.add_accel_group(accel_group)

        for menu in menus:
            menu_bar.append(self.get_menu(menu, widget_manager, accel_group))

        return menu_bar

class Pinbar:
    THUMB_COUNT = 10

    def __init__(self, main_app):
        self.main_app = main_app

        self.active = False
        self.pinbar_size = None
        self.thumb_array = []
        self.target_array = []
        self.label_array = []

        factory = WidgetFactory()

        # Pinbar hbox
        self.hbox = gtk.HBox(True, 0)
        self.hbox.connect("size-allocate", self.on_size_allocate)

        for i in range(self.THUMB_COUNT):
            tvbox = gtk.VBox(False, 0)
            self.hbox.pack_start(tvbox, False, False, 1)

            th = ThumbnailViewer(1)
            self.thumb_array.append(th)
            self.target_array.append(None)
            th.fill()

            ebox = factory.get_event_box(child=th.get_widget(),
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, True, False, 0)
            
            label = gtk.Label()
            label.set_markup("<span underline='single'>%s</span>" % ((i+1) % self.THUMB_COUNT))
            self.label_array.append(label)

            ebox = factory.get_event_box(child=label,
                                         bg_color=None,
                                         on_button_press_event=self.on_th_press(i),
                                         on_scroll_event=lambda: None)
            tvbox.pack_start(ebox, False, False, 1)

    def on_size_allocate(self, widget, event, data=None):
        allocation = self.hbox.allocation
        width, height = allocation.width, allocation.height

        if self.pinbar_size != (width, height):
            self.pinbar_size = (width, height)

            new_width = (width-(self.THUMB_COUNT+1)) / self.THUMB_COUNT

            for thumb in self.thumb_array:
                thumb.set_size(new_width)

            for label in self.label_array:
                label.set_size_request(new_width, 20)

    def on_th_press(self, index):
        def handler(widget, event, data=None):
            if event.button == 1:
                self.send_to_target(index)
            else:
                self.associate_target(index)

        return handler

    def on_send_to(self, index):
        def handler(_):
            if self.is_active():
                self.send_to_target(index)
        return handler

    def on_associate(self, index):
        def handler(_):
            if self.is_active():
                self.associate_target(index)
        return handler

    def send_to_target(self, index):
        target = self.target_array[index]

        if not target:
            self.associate_target(index)
        else:
            self.main_app.move_current(target)

    def associate_target(self, index):
        def on_file_selected(selection):
            imgfile = FileFactory.create(selection)
            dirname = imgfile.get_dirname()

            thumb = self.thumb_array[index]
            thumb.load(imgfile)
            thumb.set_tooltip_text(dirname)

            self.target_array[index] = dirname
            label = "<span underline='single'>%s</span> %s" % ((index+1) % self.THUMB_COUNT, 
                                                                os.path.split(dirname)[-1])
            self.label_array[index].set_markup(label)

        FileSelectorDialog("Select target dir", 
                           self.main_app.get_base_dir(),
                           None, 
                           on_file_selected).run()

    def get_widget(self):
        return self.hbox

    def hide(self):
        self.active = False
        self.get_widget().hide()

    def show(self):
        self.active = True
        self.get_widget().show()

    def is_active(self):
        return self.active

class UndoStack:
    def __init__(self, on_push, on_stack_empty):
        self.stack = []
        self.on_push = on_push
        self.on_stack_empty = on_stack_empty

    def clear(self):
        self.stack = []

    def push(self, action):
        self.stack.append(action)
        self.on_push(action)

    def empty(self):
        return not self.stack

    def top(self): 
        return self.stack[-1]

    def pop(self):
        action = self.stack.pop()
        if self.empty():
            self.on_stack_empty()
        return action

class ViewerApp:
    DEF_WIDTH = 1024
    DEF_HEIGHT = 768
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
        self.undo_stack = UndoStack(self.on_undo_stack_push, 
                                    self.on_undo_stack_empty)

        self.embedded_app = None
        self.fullview_active = False

        ### Window composition
        factory = WidgetFactory()
        self.widget_manager = WidgetManager()

        self.window = factory.get_window(width=self.DEF_WIDTH, 
                                         height=self.DEF_HEIGHT,
                                         on_destroy=self.on_destroy,
                                         on_key_press_event=self.on_key_press_event)

        # Main vbox of the window (contains pinbar hbox, viewer hbox and status bar hbox)
        vbox = gtk.VBox(False, 0)
        self.window.add(vbox)

        # Must be instatiated first to associate the accelerators:
        self.pinbar = Pinbar(self)

        # Menubar
        menus = self.get_menubar_entries(self.pinbar)
        self.menu_bar = factory.get_menu_bar(self.window, self.widget_manager, menus)
        vbox.pack_start(self.menu_bar, False, False, 0)

        # Toolbar
        self.load_icons() # load icons first
        self.toolbar = self.build_toolbar(self.widget_manager)
        vbox.pack_start(self.toolbar, False, False, 0)

        # Pinbar (pack it AFTER the toolbar)
        vbox.pack_start(self.pinbar.get_widget(), False, False, 0)

        # Viewer hbox
        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, True, True, 0)

        # Left thumbnail
        self.go_back_icon = factory.get_image_from_stock(gtk.STOCK_GO_BACK, 1)
        ebox = factory.get_event_box(child=self.go_back_icon,
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

        self.go_forward_icon = factory.get_image_from_stock(gtk.STOCK_GO_FORWARD, 1)
        ebox = factory.get_event_box(child=self.go_forward_icon,
                                     bg_color=self.BG_COLOR,
                                     on_button_press_event=self.on_th_next_press,
                                     on_scroll_event=self.on_th_scroll)
        hbox.pack_start(ebox, False, False, 0)

        # Status Bar:
        self.status_bar = gtk.HBox(False, 0)
        vbox.pack_start(self.status_bar, False, False, 5)

        self.file_info = gtk.Label()
        self.file_index = gtk.Label()

        self.status_bar.pack_start(self.file_info, False, False, 10)
        self.status_bar.pack_end(self.file_index, False, False, 10)

        # Window composition end

        if files:
            self.set_files(files, start_file)
        else:
            open_dialog = OpenDialog(initial_dir=".", 
                                     callback=self.on_file_selected)
            open_dialog.run()

            if self.file_manager.empty():
                raise Exception("No files selected!")

        # Show main window AFTER obtaining file list
        self.window.show_all()
        self.window.set_focus(None)

    def get_menubar_entries(self, pinbar):
        pinbar_send = lambda i: {"text" : "Bucket %i" % ((i+1)%10),
                                 "accel" : "%i" % ((i+1)%10),
                                 "handler" : pinbar.on_send_to(i)}
        pinbar_assoc = lambda i: {"text" : "Bucket %i" % ((i+1)%10),
                                  "accel" : "<Control>%i" % ((i+1)%10),
                                  "handler" : pinbar.on_associate(i)}

        # XXX proper behavior of "Right/Left"
        # XXX disable reuse menuitem and toolbutton if no prev target
        return [{"text" : "_File",
                 "items" : [{"stock" : gtk.STOCK_OPEN,
                             "accel" : "O",
                             "handler" : self.on_open_file},
                            {"separator" : True},
                            {"text" : "Rename",
                             "accel" : "<Control>M",
                             "handler" : self.on_rename_current},
                            {"stock" : gtk.STOCK_DELETE,
                             "accel" : "K",
                             "handler" : self.on_delete_current},
                            {"separator" : True},
                            {"text" : "Open in external viewer",
                             "accel" : "X",
                             "handler" : self.on_external_open},
                            {"text" : "Open in embedded viewer",
                             "accel" : "E",
                             "key" : "embedded_mitem",
                             "handler" : self.on_embedded_open},
                            {"toggle" : "Enable animation",
                             "accel" : "G",
                             "key" : "animation_toggle",
                             "handler" : self.on_enable_animation},
                            {"separator" : True},
                            {"stock" : gtk.STOCK_QUIT,
                             "accel" : "Q",
                             "handler" : self.on_quit_app}]},
                {"text" : "_Edit",
                 "items" : [{"stock" : gtk.STOCK_UNDO,
                             "accel" : "U",
                             "key" : "undo_mitem",
                             "sensitive" : False,
                             "handler" : self.on_undo},
                            {"separator" : True},
                            {"toggle" : "Star image",
                             "key" : "star_toggle",
                             "accel" : "S",
                             "handler" : self.on_toggle_star},
                            {"separator" : True},
                            {"text" : "Select base directory",
                             "accel" : "B",
                             "handler" : self.on_select_base_dir},
                            {"text" : "Move to target",
                             "accel" : "M",
                             "handler" : self.on_move_to_target},
                            {"text" : "Reuse last target",
                             "accel" : (gtk.keysyms.period, 0),
                             "handler" : self.on_reuse_target}]},
                {"text" : "_View",
                 "items" : [{"toggle" : "Show toolbar",
                             "active" : True,
                             "accel" : "A",
                             "key" : "toolbar_toggle",
                             "handler" : self.on_toggle_toolbar},
                            {"toggle" : "Show thumbnails",
                             "active" : True,
                             "accel" : "T",
                             "key" : "thumbnails_toggle",
                             "handler" : self.on_toggle_thumbnails},
                            {"toggle" : "Show status bar",
                             "active" : True,
                             "accel" : "C",
                             "key" : "status_bar_toggle",
                             "handler" : self.on_toggle_status_bar},
                            {"separator" : True},
                            {"toggle" : "Zoom to fit",
                             "active" : True,
                             "accel" : "Z",
                             "key" : "zoom_to_fit_toggle",
                             "handler" : self.on_toggle_zoom},
                            {"stock" : gtk.STOCK_ZOOM_IN,
                             "accel" : (gtk.keysyms.plus, 0),
                             "handler" : self.on_zoom_in},
                            {"stock" : gtk.STOCK_ZOOM_OUT,
                             "accel" : (gtk.keysyms.minus, 0),
                             "handler" : self.on_zoom_out},
                            {"separator" : True},
                            {"toggle" : "Fullscreen",
                             "accel" : "L",
                             "key" : "fullscreen_toggle",
                             "handler" : self.on_toggle_fullscreen}]},
                {"text" : "_Image",
                 "items" : [{"text" : "Rotate clockwise",
                             "accel" : "R",
                             "handler" : self.on_rotate_c},
                            {"text" : "Rotate counter-clockwise",
                             "accel" : "<Control>R",
                             "handler" : self.on_rotate_cc},
                            {"separator" : True},
                            {"text" : "Flip horizontal",
                             "accel" : "F",
                             "handler" : self.on_flip_horizontal},
                            {"text" : "Flip vertical",
                             "accel" : "<Control>F",
                             "handler" : self.on_flip_vertical}]},
                {"text" : "_Go",
                 "items" : [{"stock" : gtk.STOCK_GOTO_FIRST,
                             "accel" : "H",
                             "handler" : self.on_goto_first},
                            {"stock" : gtk.STOCK_GOTO_LAST,
                             "accel" : "End",
                             "handler" : self.on_goto_last},
                            {"separator" : True},
                            {"stock" : gtk.STOCK_GO_FORWARD,
                             "accel" : "Right",
                             "handler" : self.on_go_forward},
                            {"stock" : gtk.STOCK_GO_BACK,
                             "accel" : "Left",
                             "handler" : self.on_go_back},
                            {"separator" : True},
                            {"text" : "Jump forward",
                             "accel" : "<Alt>Right",
                             "handler" : self.on_jump_forward},
                            {"stock" : "Jump back",
                             "accel" : "<Alt>Left",
                             "handler" : self.on_jump_back},
                            {"separator" : True},
                            {"menu" : {"text" : "Sort by ...",
                                       "items" : [{"toggle" : "Sort by name",
                                                   "accel" : "N",
                                                   "key" : "sort_by_name_toggle",
                                                   "handler" : self.on_sort_by_name},
                                                  {"toggle" : "Sort by date",
                                                   "accel" : "D",
                                                   "key" : "sort_by_date_toggle",
                                                   "handler" : self.on_sort_by_date},
                                                  {"separator" : True},
                                                  {"toggle" : "Inverted order",
                                                   "key" : "inverted_order_toggle",
                                                   "sensitive" : False,
                                                   "accel" : "I",
                                                   "handler" : self.on_toggle_sort_order}]}}]},
                {"text" : "_Pinbar",
                 "items" : [{"toggle" : "Show pinbar",
                             "accel" : "P",
                             "active" : True,
                             "key" : "pinbar_toggle",
                             "handler" : self.on_show_pinbar},
                            {"separator" : True},
                            {"menu" : {"text" : "Send to",
                                       "items" : [pinbar_send(0), pinbar_send(1), 
                                                  pinbar_send(2), pinbar_send(3), 
                                                  pinbar_send(4), pinbar_send(5), 
                                                  pinbar_send(6), pinbar_send(7), 
                                                  pinbar_send(8), pinbar_send(9),]}},
                            {"menu" : {"text" : "Associate",
                                       "items" : [pinbar_assoc(0), pinbar_assoc(1), 
                                                  pinbar_assoc(2), pinbar_assoc(3), 
                                                  pinbar_assoc(4), pinbar_assoc(5), 
                                                  pinbar_assoc(6), pinbar_assoc(7), 
                                                  pinbar_assoc(8), pinbar_assoc(9)]}}]},
                {"text" : "_Help",
                 "items" : [{"stock" : gtk.STOCK_ABOUT,
                             "handler" : self.on_show_about}]}]

    def build_toolbar(self, widget_manager):
        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)

        tooltips = gtk.Tooltips()
        toolbar.set_tooltips(True)
        
        button = gtk.ToolButton(gtk.STOCK_OPEN)
        button.connect("clicked", self.on_open_file)
        button.set_tooltip(tooltips, "Open")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_SAVE_AS)
        button.connect("clicked", self.on_rename_current)
        button.set_tooltip(tooltips, "Rename")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_DELETE)
        button.connect("clicked", self.on_delete_current)
        button.set_tooltip(tooltips, "Delete")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton(gtk.STOCK_UNDO)
        handler_id = button.connect("clicked", self.on_undo)
        button.set_tooltip(tooltips, "Undo")
        button.set_sensitive(False)
        widget_manager.add_widget("undo_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToggleToolButton(gtk.STOCK_ABOUT)
        handler_id = button.connect("clicked", self.on_toggle_star)
        button.set_tooltip(tooltips, "Star")
        widget_manager.add_widget("star_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_INDENT)
        button.connect("clicked", self.on_move_to_target)
        button.set_tooltip(tooltips, "Move")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_REFRESH)
        button.connect("clicked", self.on_reuse_target)
        button.set_tooltip(tooltips, "Reuse")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton(gtk.STOCK_EXECUTE)
        button.connect("clicked", self.on_external_open)
        button.set_tooltip(tooltips, "External open")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_CONVERT)
        handler_id = button.connect("clicked", self.on_embedded_open)
        button.set_tooltip(tooltips, "Embedded open")
        widget_manager.add_widget("embedded_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton(gtk.STOCK_MEDIA_PLAY)
        handler_id = button.connect("clicked", self.on_enable_animation)
        button.set_tooltip(tooltips, "Enable animation")
        widget_manager.add_widget("animation_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToggleToolButton(gtk.STOCK_ZOOM_FIT)
        button.set_active(True)
        handler_id = button.connect("clicked", self.on_toggle_zoom)
        button.set_tooltip(tooltips, "Toggle zoom mode")
        widget_manager.add_widget("zoom_to_fit_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_ZOOM_IN)
        button.connect("clicked", self.on_zoom_in)
        button.set_tooltip(tooltips, "Zoom in")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_ZOOM_OUT)
        button.connect("clicked", self.on_zoom_out)
        button.set_tooltip(tooltips, "Zoom out")
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton(gtk.STOCK_FULLSCREEN)
        handler_id = button.connect("clicked", self.on_toggle_fullscreen)
        button.set_tooltip(tooltips, "Enable fullscreen")
        widget_manager.add_widget("fullscreen_button", button, handler_id)
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = gtk.ToolButton("rotate-counter-clockwise")
        button.connect("clicked", self.on_rotate_cc)
        button.set_tooltip(tooltips, "Rotate counter-clockwise")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("rotate-clockwise")
        button.connect("clicked", self.on_rotate_c)
        button.set_tooltip(tooltips, "Rotate clockwise")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("flip-horizontal")
        button.connect("clicked", self.on_flip_horizontal)
        button.set_tooltip(tooltips, "Flip horizontal")
        toolbar.insert(button, -1)

        button = gtk.ToolButton("flip-vertical")
        button.connect("clicked", self.on_flip_vertical)
        button.set_tooltip(tooltips, "Flip vertical")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToolButton(gtk.STOCK_GOTO_FIRST)
        button.connect("clicked", self.on_goto_first)
        button.set_tooltip(tooltips, "Go to first file")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GOTO_LAST)
        button.connect("clicked", self.on_goto_last)
        button.set_tooltip(tooltips, "Go to last file")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_MEDIA_REWIND)
        button.connect("clicked", self.on_jump_back)
        button.set_tooltip(tooltips, "Jump back")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_MEDIA_FORWARD)
        button.connect("clicked", self.on_jump_forward)
        button.set_tooltip(tooltips, "Jump forward")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GO_BACK)
        button.connect("clicked", self.on_go_back)
        button.set_tooltip(tooltips, "Previous")
        toolbar.insert(button, -1)

        button = gtk.ToolButton(gtk.STOCK_GO_FORWARD)
        button.connect("clicked", self.on_go_forward)
        button.set_tooltip(tooltips, "Next")
        toolbar.insert(button, -1)

        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        button = gtk.ToggleToolButton(gtk.STOCK_ITALIC)
        handler_id = button.connect("clicked", self.on_sort_by_name)
        button.set_tooltip(tooltips, "Sort by name")
        widget_manager.add_widget("sort_by_name_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToggleToolButton("sort-by-date")
        handler_id = button.connect("clicked", self.on_sort_by_date)
        button.set_tooltip(tooltips, "Sort by date")
        widget_manager.add_widget("sort_by_date_button", button, handler_id)
        toolbar.insert(button, -1)

        button = gtk.ToolButton("sort-ascending")
        handler_id = button.connect("clicked", self.on_toggle_sort_order)
        button.set_tooltip(tooltips, "Toggle sort order")
        button.set_sensitive(False)
        widget_manager.add_widget("inverted_order_button", button, handler_id)
        toolbar.insert(button, -1)

        return toolbar

    def load_icons(self):
        factory = gtk.IconFactory()

        icons = [("rotate-clockwise", "icons/rotate-clockwise.png"),
                 ("rotate-counter-clockwise", "icons/rotate-counter-clockwise.png"),
                 ("flip-horizontal", "icons/flip-horizontal.png"),
                 ("flip-vertical", "icons/flip-vertical.png"),
                 ("sort-by-date", "icons/sort-by-date.png"),
                 ("sort-ascending", "icons/sort-ascending.png"),
                 ("sort-descending", "icons/sort-descending.png")]

        for icon_id, filename in icons:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            iconset = gtk.IconSet(pixbuf)
            factory.add(icon_id, iconset)

        factory.add_default()


    def set_files(self, files, start_file):
        self.file_manager.set_files(files)

        self.undo_stack.clear()

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
        self.on_go_back(None)

    def on_th_next_press(self, widget, event, data=None):
        self.on_go_forward(None)

    def on_th_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            self.on_go_back(None)
        else:
            self.on_go_forward(None)

    # not real gtk events:
    def on_viewer_drag_left(self): self.on_go_back(None)
    def on_viewer_drag_right(self): self.on_go_forward(None)

    def on_viewer_scroll(self, widget, event, data=None):
        if event.direction == gtk.gdk.SCROLL_UP:
            factor = 1.05
        else:
            factor = 0.95

        old_size = self.image_viewer.get_scaled_size()

        self.widget_manager.get("zoom_to_fit_toggle").set_active(False)
        self.widget_manager.get("zoom_to_fit_button").set_active(False)
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

        self.undo_stack.push(self.file_manager.rename_current(new_name))

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

    def on_undo_stack_push(self, item):
        self.widget_manager.get("undo_mitem").set_sensitive(True)
        self.widget_manager.get("undo_button").set_sensitive(True)

    def on_undo_stack_empty(self):
        self.widget_manager.get("undo_mitem").set_sensitive(False)
        self.widget_manager.get("undo_button").set_sensitive(False)
    ## 

    ## Internal helpers
    def move_current(self, target_dir):
        if target_dir in self.last_targets:
            self.last_targets.remove(target_dir)

        self.last_targets.insert(0, target_dir)

        self.undo_stack.push(self.file_manager.move_current(target_dir))

    def stop_embedded_app(self):
        if self.embedded_app:
            os.kill(self.embedded_app, signal.SIGTERM)
            self.embedded_app = None
            self.window.queue_draw() # force to window to fully redraw

    def reload_viewer(self, force_stop=True):
        if force_stop:
            self.stop_embedded_app()

        current_file = self.file_manager.get_current_file()
        anim_enabled = self.widget_manager.get("animation_toggle").get_active()
        current_file.set_anim_enabled(anim_enabled)

        # Handle star toggle
        with self.widget_manager.get_blocked("star_toggle") as star_toggle:
            star_toggle.set_active(current_file.is_starred()) 

        with self.widget_manager.get_blocked("star_button") as star_button:
            star_button.set_active(current_file.is_starred()) 

        # Update main viewer and thumbnails
        self.image_viewer.load(current_file)
        self.th_left.load(self.file_manager.get_prev_file())
        self.th_right.load(self.file_manager.get_next_file())

        # Handle embedded buttons
        self.widget_manager.get("embedded_mitem").set_sensitive(current_file.can_be_embedded())
        self.widget_manager.get("embedded_button").set_sensitive(current_file.can_be_embedded())

        # Reset zoom toggle
        self.widget_manager.get("zoom_to_fit_toggle").set_active(True)
        self.widget_manager.get("zoom_to_fit_button").set_active(True)

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

        file_info = "<i>Date:</i> %s | <i>Dimensions:</i> %s pixels | <i>Size:</i> %s | <i>Zoom:</i> %d%%\n<i>SHA1:</i> %s" % \
                    (image_file.get_mtime(),
                     image_file.get_dimensions(),
                     image_file.get_filesize(), 
                     self.image_viewer.get_zoom_factor(),
                     image_file.get_sha1())

        file_info += "\n<i>Base directory:</i> <b>%s</b>" % self.base_dir

        if self.last_targets:
            file_info += "\n<i>Last directory:</i> <b>%s</b>" % self.last_targets[0]

        if not self.undo_stack.empty():
            last_action = self.undo_stack.top()
            background, foreground = {
                Action.NORMAL : ("green", None),
                Action.WARNING : ("yellow", None),
                Action.DANGER : ("red", "white")
            }[last_action.severity]
            span = "<span"
            if background: span += " background='%s'" % background
            if foreground: span += " foreground='%s'" % foreground
            span += ">%s</span>" % last_action.description
            file_info += "\n<i>Last action:</i> " + span

        inverse_order = self.widget_manager.get("inverted_order_toggle").active
        file_index = "<b><big>%d/%d</big></b>\n<i>Order:</i> %s %s" % \
                     (self.file_manager.get_current_index() + 1, 
                      self.file_manager.get_list_length(),
                      self.files_order,
                      "Desc" if inverse_order else "Asc")

        rss, vsize = get_process_memory_usage()
        file_index += "\n<i>RSS:</i> %s\n<i>VSize:</i> %s" % (Size(rss), Size(vsize))

        self.file_info.set_markup(file_info)
        self.file_index.set_markup(file_index)
        self.file_index.set_justify(gtk.JUSTIFY_RIGHT)

    def reorder_files(self):
        inverse_order = self.widget_manager.get("inverted_order_toggle").active

        if self.files_order == "Date":
            self.file_manager.sort_by_date(inverse_order)
        elif self.files_order == "Name":
            self.file_manager.sort_by_name(inverse_order)
        else:
            assert(False)

    def quit_app(self):
        self.stop_embedded_app()
        gtk.Widget.destroy(self.window)
    ##

    ## Key Bindings
    def get_key_bindings(self):
        bindings = {
            ## Generic actions:
            "Escape"      : self.quit_app,

            ## Image:
            "v"           : lambda: self.on_toggle_fullview(None),

            ## Files navigation:
            "Right"       : lambda: self.on_go_forward(None),
            "Left"        : lambda: self.on_go_back(None),
        }

        return bindings

    ## action handlers
    def on_quit_app(self, _):
        self.quit_app()

    def on_show_about(self, _):
        about = AboutDialog(self.window)
        about.show()

    def on_toggle_fullscreen(self, toggle):
        if toggle.get_active():
            self.window.fullscreen()
        else:
            self.window.unfullscreen()

        self.widget_manager.get("fullscreen_toggle").set_active(toggle.get_active())
        self.widget_manager.get("fullscreen_button").set_active(toggle.get_active())

    def on_toggle_fullview(self, _):
        fullscreen_on = self.widget_manager.get("fullscreen_toggle").active
        toolbar_on = self.widget_manager.get("toolbar_toggle").active
        pinbar_on = self.widget_manager.get("pinbar_toggle").active
        thumbnails_on = self.widget_manager.get("thumbnails_toggle").active
        status_bar_on = self.widget_manager.get("status_bar_toggle").active

        if not self.fullview_active:
            if not fullscreen_on:
                self.window.fullscreen()
            self.menu_bar.hide()
            self.toolbar.hide()
            self.pinbar.hide()
            self.go_back_icon.hide()
            self.go_forward_icon.hide()
            self.th_left.hide()
            self.th_right.hide()
            self.status_bar.hide()
            self.fullview_active = True
        else:
            if not fullscreen_on:
                self.window.unfullscreen()
            self.menu_bar.show()
            if toolbar_on:
                self.toolbar.show()
            if pinbar_on:
                self.pinbar.show()
            self.go_back_icon.show()
            self.go_forward_icon.show()
            if thumbnails_on:
                self.th_left.show()
                self.th_right.show()
            if status_bar_on:
                self.status_bar.show()
            self.fullview_active = False

    def on_toggle_toolbar(self, toggle):
        if toggle.active:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def on_toggle_thumbnails(self, toggle):
        if toggle.active:
            self.th_left.show()
            self.th_right.show()
        else:
            self.th_left.hide()
            self.th_right.hide()

    def on_toggle_status_bar(self, toggle):
        if toggle.active:
            self.status_bar.show()
        else:
            self.status_bar.hide()

    def on_show_pinbar(self, toggle):
        if toggle.active:
            self.pinbar.show()
        else:
            self.pinbar.hide()

    def on_goto_first(self, _):
        self.file_manager.go_first()

    def on_goto_last(self, _):
        self.file_manager.go_last()

    def on_jump_forward(self, _):
        self.file_manager.go_forward(10)

    def on_jump_back(self, _):
        self.file_manager.go_backward(10)

    def on_go_forward(self, _):
        self.file_manager.go_forward(1)

    def on_go_back(self, _):
        self.file_manager.go_backward(1)

    def get_base_dir(self):
        if self.base_dir:
            return self.base_dir
        else:
            return self.file_manager.get_current_file().get_dirname()

    def on_move_to_target(self, _):
        selector = TargetSelectorDialog(initial_dir=self.get_base_dir(), 
                                        last_targets=self.last_targets, 
                                        callback=self.on_target_selected)
        selector.run()

    def on_open_file(self, _):
        initial_dir = self.file_manager.get_current_file().get_dirname()
        open_dialog = OpenDialog(initial_dir, self.on_file_selected)
        open_dialog.run()

    def on_rename_current(self, _):
        filename = self.file_manager.get_current_file().get_filename()
        renamer = RenameDialog(filename, self.on_new_name_selected)
        renamer.run()

    def on_select_base_dir(self, _):
        selector = BasedirSelectorDialog(initial_dir=self.get_base_dir(), 
                                         last_targets=[], 
                                         callback=self.on_base_dir_selected)
        selector.run()

    def on_reuse_target(self, _):
        if not self.last_targets:
            InfoDialog(self.window, "There isn't a selected target yet").run()
            return

        self.move_current(self.last_targets[0])

    def on_undo(self, _):
        if self.undo_stack.empty():
            InfoDialog(self.window, "Nothing to undo!").run()
            return

        action = self.undo_stack.pop()
        action.undo()

    def on_toggle_star(self, _):
        self.undo_stack.push(self.file_manager.toggle_star())

    def on_delete_current(self, _):
        self.undo_stack.push(self.file_manager.delete_current())

    def on_sort_by_date(self, widget):
        self.files_order = "Date"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_date_toggle", True),
                                  ("sort_by_date_button", True),
                                  ("sort_by_name_toggle", False),
                                  ("sort_by_name_button", False)]:
            with self.widget_manager.get_blocked(widget_id) as widget:
                widget.set_active(active)

        self.reorder_files()

    def on_sort_by_name(self, widget):
        self.files_order = "Name"

        self.widget_manager.get("inverted_order_toggle").set_sensitive(True)
        self.widget_manager.get("inverted_order_button").set_sensitive(True)

        for widget_id, active in [("sort_by_name_toggle", True),
                                  ("sort_by_name_button", True),
                                  ("sort_by_date_toggle", False),
                                  ("sort_by_date_button", False)]:
            with self.widget_manager.get_blocked(widget_id) as widget:
                widget.set_active(active)

        self.reorder_files()

    def on_toggle_sort_order(self, widget):
        if not self.files_order:
            return

        inverted_order_toggle = self.widget_manager.get("inverted_order_toggle")
        inverted_order_button = self.widget_manager.get("inverted_order_button")

        if widget is inverted_order_button:
            inverted_order_toggle.set_active(not inverted_order_toggle.get_active())

        if inverted_order_toggle.get_active():
            inverted_order_button.set_stock_id("sort-descending")
        else:
            inverted_order_button.set_stock_id("sort-ascending")

        self.reorder_files()

    def on_external_open(self, _):
        current_file = self.file_manager.get_current_file()
        current_file.external_open()

    def on_embedded_open(self, _):
        current_file = self.file_manager.get_current_file()
        if self.embedded_app:
            self.reload_viewer(force_stop=True)
        else:
            self.embedded_app = current_file.embedded_open(self.window.get_window().xid)
            self.reload_viewer(force_stop=False)

    def on_enable_animation(self, toggle):
        self.widget_manager.get("animation_toggle").set_active(toggle.get_active())
        self.widget_manager.get("animation_button").set_active(toggle.get_active())
        self.reload_viewer(force_stop=False)

    def on_toggle_zoom(self, toggle):
        if toggle.get_active():
            self.fit_viewer(force=True)
        else:
            self.image_viewer.zoom_at(100)

        self.widget_manager.get("zoom_to_fit_toggle").set_active(toggle.get_active())
        self.widget_manager.get("zoom_to_fit_button").set_active(toggle.get_active())

        self.refresh_info()

    def on_zoom_in(self, _):
        self.widget_manager.get("zoom_to_fit_toggle").set_active(False)
        self.widget_manager.get("zoom_to_fit_button").set_active(False)
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 1.05)
        self.refresh_info()

    def on_zoom_out(self, _):
        self.widget_manager.get("zoom_to_fit_toggle").set_active(False)
        self.widget_manager.get("zoom_to_fit_button").set_active(False)
        self.image_viewer.zoom_at(self.image_viewer.get_zoom_factor() * 0.95)
        self.refresh_info()

    def on_rotate_c(self, _):
        self.image_viewer.rotate_c()

    def on_rotate_cc(self, _):
        self.image_viewer.rotate_cc()

    def on_flip_horizontal(self, _):
        self.image_viewer.flip_horizontal()

    def on_flip_vertical(self, _):
        self.image_viewer.flip_vertical()

    ##

    def run(self):
        gtk.main()

