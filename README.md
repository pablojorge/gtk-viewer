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

By pressing the 'E' key, if the current file is an animated GIF file, animation will start. That setting is persistent, so if you switch to another GIF file it will also be animated, until animation is toggled off again with the 'E' key. 

For video files, pressing the 'e' key will embed a video player in the main window, but it's not permanent, so if you switch to a new video, the embedded player will be killed and will have to be started again with the 'e' key.

## Moving files

The idea is to make it easy to distribute a big set of files into different directories. The first step is to select a base directory. Once the base directory is selected (B), every time a new target directory is selected, it will be relative to the base dir. When the 'M' key is pressed, a directory selection dialog will be presented, starting in the base directory. Once a directory is selected, the current file will be moved to that dir. 

### Auto-handling of conflicts

If an identical file is located in the selected target dir (a file with the same name and contents), the file instead of being moved, will be automatically deleted to avoid duplicates. If there is already a file in the target directory with the same name of the current file, but having different checksums, the new file will be automatically renamed with a suffix.

### Undo/repeat

If a file is moved, auto-renamed or deleted, the action will be displayed in the status area, and can be undone by pressing the 'U' key. If you just want to repeat the last action (moving the current file to the last selected dir), you can press the '.' key. 

## Requirements

* __pdfimages__ ("xpdf-tools" port in Macports, in Ubuntu is usually already installed)
* __ffmpeg__ ("ffmpeg" in both Ubuntu and Macports)

## Features summary

### File types support

It supports previewing the following kind of files:

* Images (every file format supported by GDK Pixbuf)
* Animated GIFs
* Video (.avi, .mp4, .flv, .wmv, .mpg, .mov, .m4v)
* PDFs
* EPUBs

### Actions

* __Image manipulation__
 * __Rotation__ (R: clockwise, Control-R: counter-clockwise)
 * __Zooming__ (Z: toggle zoom-to-fit/100%, +/-/mouse scroll: adjust zoom)
 * __Vertical/horizontal flip__ (F: horizontal, Control-F: vertical)

* __File management__
 * __Select base dir__ (B)
 * __Delete__ (_Linux only_) (K) 
 * __File move__ (M)
 * __File rename__ (Control-M)
 * __Starring/unstarring__ (S)
 * __Undo__ (U)
 * __Repeat last action__ ('.', Enter)
 * __Open__ (Control-O)
 * __Toggle pinbar__ (P)
 * __Send to bucket 'n'__ (1-0)
 * __Associate target of bucket 'n'__ (Control 1-0)

* __Navigation__
 * __Open with external viewer__ (X)
 * __Enable/disable embedded preview__ (E)
 * __Sort by date__ (D)
 * __Sort by name__ (N)
 * __Invert sort order__ (I)
 * __Fullscreen__ (L)
 * __Toggle thumbnails__ (T)
 * __Go forward/back__ (Right, Left)
 * __Goto first/last__ (H, End)

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
