import os

import urllib2

class MultiDownloader:
    def __init__(self, url_pattern, initial, final):
        self.url_pattern = url_pattern
        self.initial = initial
        self.final = final

    def run(self, tmp_dir):
        bufsize = 8192

        total = self.final - self.initial + 1
        for index in range(self.initial, self.final + 1):
            current = index - self.initial + 1
            try:
                url = self.url_pattern % index
                basename = os.path.basename(url)
                response = urllib2.urlopen(url)
                size = int(response.info().getheader("Content-Length"))
                read = 0
                with open(os.path.join(tmp_dir, basename), "w") as output:
                    data = response.read(bufsize)
                    while data:
                        read += len(data)
                        yield ("Downloading %d/%d..." % (current, total), 
                               (current-1 + float(read)/size) / (total))
                        output.write(data)
                        data = response.read(bufsize)
            except Exception, e:
                yield ("Error %d/%d: %s" % (current, total, e), 
                       float(current-1) / (total))

