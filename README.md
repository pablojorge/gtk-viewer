# GTK Viewer

Simple multimedia viewer written in Python. I created it to organize large collections of files, so my main goal was to make it comfortable to use (it has many single-key shortcuts) and to be versatile, so it can preview many different types of images, animated GIFs, PDF files, EPub files, video files, and so on.

## Viewing files

The main screen shows the current file and a thumbnail of the previous and the next file. To jump to the previous or next image, you can click or scroll over the thumbnail. Scrolling makes switching images very fast. On the bottom of the screen there are many pieces of information:

* File metadata (file size, image dimensions, checksum, date & time)
* Zoom level
* Base directory
* Last directory
* Last action
* Image index and total number of files
* Current order (by date/name ascending or descending)

On the top of the window there's a menubar, a toolbar with the most common operations, and the pinbar. The pinbar provides quick-access to a small subset of target directories. Each contains a custom thumbnail from each target directory, and can be used to quickly move the current file to that directory. The name of the current file is in both the window title and below the image.

### Special files

Video files are previewed selecting a frame located at approximately 20% of the duration of the video. GIF files are first previewed showing only the first frame. PDF files are previewed extracting the image of the first page, and EPUB files are previewed by extracting the cover image. For PDFs, the first image is extracted and its assumed to be the front cover of a magazine or e-Book.

By pressing the 'G' key, if the current file is an animated GIF file, animation will start. That setting is persistent, so if you switch to another GIF file it will also be animated, until animation is toggled off again. 

The contents from video and PDF files can be extracted pressing the 'E' key. A separate window will be opened with all the extracted frames (1 per second) in the case of video files, or all the extracted images from a PDF (pages in a magazine or e-Book).

## Moving files

The idea is to make it easy to distribute a big set of files into different directories. The first step is to select a base directory. Once the base directory is selected (B), every time a new target directory is selected, it will be relative to the base dir. When the 'M' key is pressed, a directory selection dialog will be presented, starting in the base directory. Once a directory is selected, the current file will be moved to that dir. The last selection can be reused with the '.' key. Every time the target selection dialog is shown, on the left there's a list with all the targets already used in this session, ordered by name.

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
 * __Repeat last action__ ('.')
 * __Open__ (O)
 * __Toggle pinbar__ (P)
 * __Send to bucket 'n'__ (1-0)
 * __Associate target of bucket 'n'__ (Control 1-0)

* __Navigation__
 * __Open with external viewer__ (X)
 * __Extract contents__ (E)
 * __Enable/disable GIF animation__ (E)
 * __Sort by date__ (D)
 * __Sort by name__ (N)
 * __Invert sort order__ (I)
 * __Fullscreen__ (L)
 * __Image fullview__ (V)
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

    Usage: main.py [options] FILE...

    Options:
      -h, --help            show this help message and exit
      -r, --recursive       
      -c, --check           
      -s, --stats           
      -b BASE_DIR, --base-dir=BASE_DIR
      
### Recursivity:

If the '-r' or '--recursive' arguments are given, the specified dirs will be scanned recursively and all the compatible files will be included in the list.

### Check

The specified dirs will be scanned to see whether there are unorganized files (directories containing both regular files and sub-directories), or empty directories.

### Stats

In this mode, the program will just print the total number of files by type.

### Base dir

This parameter pre-sets the base dir. Can be modified later with the 'B' key.
