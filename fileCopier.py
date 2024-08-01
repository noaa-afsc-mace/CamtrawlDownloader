'''
fileCopier copies a list of files.

name - a string that identifies the worker. This string is
       emitted with signals to differentiate them.

fileList - a list of files to copy. Only the file names.
           Do not include the full path.

srcPath - The source path. Where to copy from.

destPath - The destination path. Where to copy to.

parent - the QObject that serves as the parent who would
         send the "abort" signal.

verify - if True, source and dest files will be compared
         using MD5 hashing to verify integrity. Results
         are returned in the "finished" signal

matchTimes - if True, source files create and modified times
             will be copied to dest file.


SIGNALS

error = QtCore.pyqtSignal(workerName, fileName, errorString)

progress = QtCore.pyqtSignal(workerName, pctComplete, lastFileCopied)

complete = QtCore.pyqtSignal(workerName, nFilescopied,
        {'fileList':[], 'hash':[]}, nFilesError, {'fileList':[], 'error':[]})


'''


import os
import shutil
import win32file
from hashlib import md5
from PyQt6 import QtCore


#  pyQt worker objects should subclass QObject
class fileCopier(QtCore.QObject):

    #  define signals
    error = QtCore.pyqtSignal(str, str, str)
    progress = QtCore.pyqtSignal(str, int, str)
    complete = QtCore.pyqtSignal(str, int, dict, int, dict)
    aborted = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, name, fileList, srcPath, destPath, parent, verify=False,
            matchTimes=False):

        #  initialize the base class
        QtCore.QObject.__init__(self)

        #  set default properties
        self.__abort = False
        self.copiedFiles = {'fileList':[], 'hash':[]}
        self.errorFiles = {'fileList':[], 'error':[]}

        #  connect our parent's signals
        parent.abort.connect(self.abort)
        parent.finished.connect(self.finish)

        #  store path and file info
        self.name = name
        self.sourcePath = os.path.normpath(srcPath)
        self.destPath = os.path.normpath(destPath)
        self.fileList = fileList
        self.verify = verify
        self.matchTimes = matchTimes


    def copyFiles(self):
        '''
        copyFiles does the work
        '''

        #  set the initial pct complete to 0
        nCopied = 0.0
        nTotal = len(self.fileList)

        #  iterate thru the files
        for file in self.fileList:
            sourceFile = self.sourcePath + os.sep + file
            destFile = self.destPath + os.sep + file

            try:
                #  copy the file
                shutil.copy2(sourceFile, self.destPath)

                #  check if we should match creation times
                if (self.matchTimes):
                    #  set the dest creation time to the source creation time

                    h = win32file.CreateFile(sourceFile, win32file.GENERIC_READ, 0,
                                             None, win32file.OPEN_EXISTING, 0, 0)
                    pt = win32file.GetFileTime(h)
                    win32file.CloseHandle(h)
                    h = win32file.CreateFile(destFile, win32file.GENERIC_WRITE, 0,
                                             None, win32file.OPEN_EXISTING, 0, 0)
                    win32file.SetFileTime(h,pt[0], pt[1], pt[2])
                    win32file.CloseHandle(h)

                #  check if we should verify copy
                if (self.verify):
                    #  compute the checksum
                    sourceHash = self.calcChecksum(sourceFile)
                    destHash = self.calcChecksum(destFile)
                    if (sourceHash != destHash):
                        #  hashes don't match - copy error
                        self.errorFiles['fileList'].append(file)
                        self.errorFiles['error'].append('MD5 Hash Error: ' + sourceHash + ' != ' + destHash)
                    else:
                        #  hashes match - mark this file as copied
                        self.copiedFiles['fileList'].append(file)
                        self.copiedFiles['hash'].append(sourceHash)

                else:
                    #  mark this file as copied
                    self.copiedFiles['fileList'].append(file)
                    self.copiedFiles['hash'].append('')

            except (IOError, os.error) as why:
                #  error copying file - emit error signal with the file name and error string
                self.error.emit(self.name, file, str(why))
                self.errorFiles['fileList'].append(file)
                self.errorFiles['error'].append(str(why))


            #  calculate our progress and emit
            nCopied = nCopied + 1.0
            pct = int(round((nCopied / nTotal) * 100.0, 2))
            self.progress.emit(self.name, pct, file)

            #  check if we should abort
            if (self.__abort):
                #  we're done here
                break

        if (not self.__abort):
            #  emit the results
            nCopied = len(self.copiedFiles['fileList'])
            nErrored = len(self.errorFiles['fileList'])
            self.complete.emit(self.name, nCopied, self.copiedFiles, nErrored, self.errorFiles)
        else:
            #  if we're aborting we just bail
            self.aborted.emit(self.name)


    def calcChecksum(self, fname):
        '''
            Calculates the MD5 hash of the provided file
        '''

        block_size = 128 * 1024
        mdf = md5()
        f = open(fname, "rb")
        while True:
            data = f.read(block_size)
            if not data:
                break
            mdf.update(data)

        return mdf.hexdigest()


    @QtCore.pyqtSlot()
    def abort(self):
        '''
        The abort slot is called when we receive the abort signal
        '''
        #  set the abort flag
        self.__abort = True


    @QtCore.pyqtSlot()
    def finish(self):
        '''
        The finish slot is called when we receive the finish signal
        '''

        self.finished.emit()
