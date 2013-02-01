import time
import gobject

from threading import Thread, Lock, Condition

# Run this once during application start:
gobject.threads_init()

# Dirty trick to make up for the lack of a "yield" operation:
def yield_processor():
    time.sleep(0.000001)

# Use this thread to postpone work and update the GUI asynchronously.
# The idea is to push a function and some parameters, and that function
# will be executed in a separate thread. This function must NOT update
# the UI directly, it must return another function with its own arguments
# to be queued in the main thread's event loop with gobject.idle_add. 
# (See http://faq.pygtk.org/index.py?file=faq20.006.htp&req=show)
class Worker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.lock = Lock()
        self.cond = Condition(self.lock)
        self.stopped = False
        self.queue = []

    def run(self):
        while True:
            job = None
            with self.cond:
                if self.stopped:
                    return
                if not self.queue:
                    self.cond.wait()
                else:
                    job, params = self.queue.pop(0)
            if not job:
                continue
            self.execute(job, params)

    def execute(self, job, params):
        try:
            func, args = job(*params)
            # The async function may decide to NOT update
            # the UI:
            if func:
                gobject.idle_add(func, *args)
        except Exception, e:
            print "Warning:", e

    def stop(self):
        with self.cond:
            self.stopped = True
            self.cond.notify_all()

    def clear(self):
        with self.cond:
            self.queue = []
            self.cond.notify_all()

    def push(self, job):
        with self.cond:
            self.queue.append(job)
            self.cond.notify_all()

class Updater(Thread):
    def __init__(self, generator, on_progress, on_finish, on_finish_args):
        Thread.__init__(self)
        self.generator = generator
        self.on_progress = on_progress
        self.on_finish = on_finish
        self.on_finish_args = on_finish_args

    def run(self):
        try:
            for progress in self.generator:
                gobject.idle_add(self.on_progress, progress)
                # give a chance to the main thread to update the 
                # progressbar: (otherwise, if there are no IO
                # operations while the generator is consumed,
                # the main thread is never run and the UI just 
                # blocks)
                yield_processor()
        except Exception, e:
            print "Warning", e

        # Execute the callback in the main thread (it's highly
        # probable that it will try to modify the UI). If we
        # run it here, many GTK assertions will fail and even
        # SIGSEGVs may be generated
        gobject.idle_add(self.on_finish, *self.on_finish_args)

        # Trick to "auto" dispose the thread: (if the on_finish 
        # callback tried to join this thread, it would deadlock)
        gobject.idle_add(lambda t: t.join(), self)

