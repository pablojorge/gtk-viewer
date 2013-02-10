import os
import string
import pexpect

import gtk

from imagefile import ImageFile, Size
from cache import cached
from system import execute

class ArchiveFile(ImageFile):
    description = "archive"
    valid_extensions = ["zip", "rar"]

    def __init__(self, filename):
        ImageFile.__init__(self, filename)
        self.delegate = self.build_delegate(filename)

    @classmethod
    def build_delegate(cls, filename):
        if filename.endswith("zip"):
            return ZIPFile(filename)
        elif filename.endswith("rar"):
            return RARFile(filename)
        else:
            return None

    @cached()
    def get_pixbuf(self):
        root_path = os.path.split(os.path.dirname(__file__))[0]
        pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(root_path, "icons/archive.png"))
        return pixbuf

    @cached()
    def get_sha1(self):
        # avoiding this for archive files
        return "Contents: %d files" % (len(self.get_metadata()) - 1)

    def get_metadata(self):
        return self.delegate.get_metadata()

    def extract_contents(self, tmp_dir):
        return self.delegate.extract_contents(tmp_dir)

    def can_be_extracted(self):
        return True

class ZIPFile:
    def __init__(self, filename):
        self.filename = filename

    @cached()
    def get_metadata(self):
        ret = [("Filename", "Size", "Date", "Time")]
        output = execute(["unzip", "-l", self.filename], check_retcode=False)
        lines = output.split("\n")
        for line in lines[3:-3]:
            tokens = map(string.strip, filter(lambda x: x, line.split(" ")))
            ret.append((string.join(tokens[3:], " "), 
                        Size(int(tokens[0])), 
                        tokens[1], 
                        tokens[2]))
        return ret

    def extract_contents(self, tmp_dir):
        try:
            child = pexpect.spawn("unzip", [self.filename, "-d", tmp_dir])
            while True:
                try:
                    child.expect("inflating")
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e

class RARFile:
    def __init__(self, filename):
        self.filename = filename

    @cached()
    def get_metadata(self):
        ret = [("Filename", "Original Size", "Packed Size", "Ratio", "Date", "Time", "Attr")]
        output = execute(["unrar", "l", "-c-", self.filename], check_retcode=False)
        lines = output.split("\n")
        for line in lines[7:-4]:
            # 0     1   2      3     4    5    6    7   8    9
            # Name Size Packed Ratio Date Time Attr CRC Meth Ver
            #      -9   -8     -7    -6   -5   -4   -3  -2   -1
            tokens = map(string.strip, filter(lambda x: x, line.split(" ")))
            ret.append((string.join(tokens[0:-9], " "),
                        Size(int(tokens[-9])),
                        Size(int(tokens[-8])),
                        tokens[-7],
                        tokens[-6],
                        tokens[-5],
                        tokens[-4]))
        return ret

    def extract_contents(self, tmp_dir):
        cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            child = pexpect.spawn("unrar", ["x", self.filename])
            while True:
                try:
                    child.expect("Extracting")
                except pexpect.TIMEOUT:
                    pass
                yield None
        except pexpect.EOF:
            pass
        except Exception, e:
            print "Warning:", e
        finally:
            os.chdir(cwd)

