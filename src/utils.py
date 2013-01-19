import os
import sys
import glob
import shutil
import subprocess

import gio

# Python tricks:
def trace(prefix):
    def decorator(func):
        def wrapper(*args):
            print "%s.%s: %s -> " % (prefix, func.__name__, args)
            ret = func(*args)
            #sys.stdout.write("%s\n" % ret)
            return ret
        return wrapper
    return decorator

# System interaction:
def execute(args, check_retcode=True):
    popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = popen.communicate()
    if check_retcode and popen.returncode != 0:
        raise Exception(str(args) + " failed!")
    return stdout + stderr

### Multi-platform functions:        
def os_switch(functions):
    os_name = os.uname()[0]

    if os_name in functions:
        function, args = functions[os_name]
        return function(*args)
    else:
        raise Exception("%s: Unsupported system" % (os_name))

def external_open(filename):
    return os_switch({
         'Linux': (external_open_linux, (filename,)),
         'Darwin': (external_open_macosx, (filename,))
    })

def get_process_memory_usage(pid=os.getpid(), pagesize=4096):
    return os_switch({
         'Linux': (get_process_memory_usage_linux, (pid, pagesize)),
         'Darwin': (get_process_memory_usage_macosx, (pid,))
    })

def trash(filename):
    return os_switch({
         'Linux': (trash_linux, (filename,)),
         # XXX Darwin support for trash
    })

def untrash(filename):
    return os_switch({
         'Linux': (untrash_linux, (filename,)),
         # XXX Darwin support for untrash
    })

### Mac OS X specific functions:
def external_open_macosx(filename):
    execute(["open", filename])

def get_process_memory_usage_macosx(pid):
    output = execute(["ps", "-v", "-p", str(pid)])
    lines = output.split('\n')
    rss, vsize = filter(lambda x:x, lines[1].split(' '))[6:8]
    return (int(rss) * 1024, int(vsize) * 1024)

### Linux specific functions:
def external_open_linux(filename):
    execute(["xdg-open", filename])

def get_process_memory_usage_linux(pid, pagesize):
    with open("/proc/%i/stat" % pid) as statfile:
        stat = statfile.read().split(' ')

        rss = int(stat[23]) * pagesize
        vsize = int(stat[22])

        return (rss, vsize)

def trash_linux(filename):
    gfile = gio.File(path=filename)
    gfile.trash()

def untrash_linux(filename):
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
                if path == os.path.abspath(filename):
                    trashed_file = info_file.replace(info_dir, files_dir)
                    trashed_file = trashed_file.replace(".trashinfo", "")
                    os.unlink(info_file)
                    shutil.move(trashed_file, filename)
                    return
    
    raise Exception("Couldn't find '%s' in trash" % filename)

