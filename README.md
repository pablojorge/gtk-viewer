# GTK Viewer

Simple multimedia viewer written in Python. I created it to organize large collections of files, so my main goal was to make it comfortable to use (it has many single-key shortcuts) and to be versatile, so it can preview many different types of images, animated GIFs, PDF files, video files, and so on.

## Viewing files

The main screen shows the current file and a thumbnail of the previous and the next file. To jump to the previous or next image, you can click or scroll over the thumbnail. Scrolling makes switching images very fast. On the bottom of the screen there are many pieces of information:

* File metadata (file size, image dimensions, checksum, date & time)
* Zoom level
* Base directory
* Last directory
* Last action
* Image index and total number of files
* Current order (by date/name ascending or descending)

### Special files

Video files are previewed selecting a frame located at approximately 20% of the duration of the video. GIF files are first previewed showing only the first frame. PDF files are previewed extracting the image of the first page, and EPUB files are previewed by extracting the cover image.

### Embedded preview

By pressing the 'e' key, if the current file is an animated GIF file, animation will start. That setting is persistent, so if you switch to another GIF file it will also be animated, until animation is toggled off again with the 'e' key. 

For video files, pressing the 'e' key will embed a video player in the main window, but it's not permanent, so if you switch to a new video, the embedded player will be killed and will have to be started again with the 'e' key.

## Moving files

The idea is to make it easy to distribute a big set of files into different directories. The first step is to select a base directory. Once the base directory is selected, every time a new target directory is selected, it will be relative to the base dir. When the 'Tab', 'l', or 'down arrow' key is pressed, a directory selection dialog will be presented, starting in the base directory. Once a directory is selected, the current file will be moved to that dir. 

### Auto-handling of conflicts

If an identical file is located in the selected target dir (a file with the same name and contents), the file instead of being moved, will be automatically deleted to avoid duplicates. If there is already a file in the target directory with the same name of the current file, but having different checksums, the new file will be automatically renamed with a suffix.

### Undo/repeat

If a file is moved, auto-renamed or deleted, the action will be displayed in the status area, and can be undone by pressing the 'u' key. If you just want to repeat the last action (moving the current file to the last selected dir), you can press the '.' or 'Enter' key. 

## Features summary

### File types support

It supports previewing the following kind of files:

* Images (every file format supported by GDK Pixbuf)
* Animated GIFs
* Video (.avi, .mp4, .flv, .wmv, .mpg, .mov, .m4v)
* PDFs

### Actions

* __Image manipulation__
 * __Rotation__ (r: clockwise, R: counter-clockwise)
 * __Zooming__ (1: zoom 100%, 0: zoom-to-fit, mouse scroll: adjust zoom)
 * __Vertical/horizontal flip__ (f: horizontal, F: vertical)

* __File management__
 * __Select base dir__ (F3)
 * __Delete/undelete__ (_Linux only_) (Delete, u)
 * __File move__ (Tab, l, down arrow)
 * __File rename__ (F2)
 * __Starring/unstarring__ (s)
 * __Repeat last action__ ('.', Enter)
 * __Open__ (o)

* __Navigation__
 * __Open with external viewer__ (x)
 * __Enable/disable embedded preview__ (e)
 * __Sort by date ascending/descending__ (d: ascending, D: descending)
 * __Sort by name ascending/descending__ (n: ascending, N: descending)
 * __Fullscreen__ (F11)
 * __Toggle thumbnails__ (F12)

### Misc features

* Recursive open
* Directory contents preview
* Image caching

## Command line arguments

Run viewer.py with '-h' or '--help' to obtain the help:

    $ python2.7 viewer.py --help

    Usage: viewer.py [options] FILE...

    Options:
      -h, --help           show this help message and exit
      -r, --recursive      
      -c, --check          
      -s, --stats          
      --base-dir=BASE_DIR  
      --allow-images       
      --allow-gifs         
      --allow-pdfs         
      --allow-videos       
      
### Recursivity:

If the '-r' or '--recursive' arguments are given, the specified dirs will be scanned recursively and all the compatible files will be included in the list.

### Check

The specified dirs will be scanned to see whether there are unorganized files (directories containing both regular files and sub-directories), or empty directories.

### Stats

In this mode, the program will just print the total number of files by type.

### File filtering

Each '--allow-<kind>' will enable the inclusion of that kind of files in the full list.
