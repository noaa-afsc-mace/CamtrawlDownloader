

import os
import sys
import datetime
import shutil
import functools
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtSql import *
import fileCopier
from ui import ui_CamTrawlDownloader
from MaceFunctions import CamtrawlMetadata

class CamtrawlDownloader(QMainWindow, ui_CamTrawlDownloader.Ui_CamTrawlDownloader):

    abort = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super(CamtrawlDownloader, self).__init__(parent)
        self.setupUi(self)

        self.isCopying = False
        self.isAborting = False
        self.isClosing = False
        self.logFile = None
        self.cameras = []

        #  create a mutex to serialize processing of finished signals
        self.mutex = QMutex()

        #  restore the application state
        self.appSettings = QSettings('afsc.noaa.gov', 'CamTrawlDownloader')
        strList = self.appSettings.value('sourcedir', [QDir.home().path()])
        self.cbSourcePath.addItems(strList)
        index = self.appSettings.value('sourceindex', -1)
        self.cbSourcePath.setCurrentIndex(index)
        self.sourceDef = self.cbSourcePath.itemText(index)
        strList = self.appSettings.value('destdir', [QDir.home().path()])
        self.cbDestPath.addItems(strList)
        index = self.appSettings.value('destindex', -1)
        self.cbDestPath.setCurrentIndex(index)
        self.destDef = self.cbSourcePath.itemText(index)
        destFolder = self.appSettings.value('destfolder', '')
        self.destFolder.setText(destFolder)
        verifyChecked = self.appSettings.value('verify', 'true')
        if verifyChecked.lower() == 'true':
            verifyChecked = True
        else:
            verifyChecked = False
        self.cbVerify.setChecked(verifyChecked)
        if (self.destFolder.text() != ''):
            enableDest = self.appSettings.value('enabledestfolder', True)
            if enableDest.lower() == 'true':
                enableDest = True
            else:
                enableDest = False
            self.cbEnableDestFolder.setChecked(enableDest)
            self.destFolder.setEnabled(enableDest)
        else:
            self.cbEnableDestFolder.setChecked(False)
            self.destFolder.setEnabled(False)
        size = self.appSettings.value('winsize', QSize(650,530))
        self.resize(size)
        position = self.appSettings.value('winposition', QPoint(50,50))
        self.move(position)

        #  check if we have both a source and dest
        if ((self.sourceDef != '') and (self.destDef != '')):
            #  we have both a source and dest - enable the download button
            self.pbDownload.setEnabled(True)

        #  create an instance of the CamTrawlMetadata class to handle reading our metadata database
        self.metadata = CamtrawlMetadata.CamTrawlMetadata()

        #  set up the signals
        self.pbSourcePath.clicked.connect(self.selectDirectory)
        self.pbDestPath.clicked.connect(self.selectDirectory)
        self.pbDownload.clicked.connect(self.startCopy)
        self.cbDestPath.currentIndexChanged[int].connect(self.cbIndexChanged)
        self.cbSourcePath.currentIndexChanged[int].connect(self.cbIndexChanged)
        self.cbEnableDestFolder.stateChanged[int].connect(self.enableSubdirClicked)

        #  set the base directory path - this is the full path to this application
        self.baseDir = functools.reduce(lambda l,r: l + os.path.sep + r,
                os.path.dirname(os.path.realpath(__file__)).split(os.path.sep))
        try:
            self.setWindowIcon(QIcon(self.baseDir + os.sep + 'resources/download.png'))
        except:
            pass


    def startCopy(self):

        #  set the copying flag
        self.isCopying = True

        #  check if this is an abort copy request
        if (self.pbDownload.text() == "Abort Download"):
            self.abortCopy()
            return

        #  change the text on our download button
        self.pbDownload.setText('Abort Download')

        #  note the starting time
        self.startTime = datetime.datetime.now()

        #  construct the source and dest paths
        sourceDir = os.path.normpath(str(self.cbSourcePath.currentText()))
        deploymentDir = (sourceDir.split(os.sep))[-1]
        destDir = os.path.normpath(str(self.cbDestPath.currentText()))
        if (self.cbEnableDestFolder.isChecked()):
            destDir = os.path.normpath(destDir + os.sep + str(self.destFolder.text()))
        destDir = destDir + os.sep + deploymentDir

        #  note if we're verifying and/or setting the file times
        if (self.cbVerify.isChecked()):
            doVerify = True
        else:
            doVerify = False

        logText = 'Preparing for download of ' + sourceDir
        self.updateLog(logText, 'black')

        #  now check if top dest dir exists
        if (os.path.exists(destDir)):
            #  destination exists - ask if we should remove
            logText = 'Found existing destination directory ' + destDir
            self.updateLog(logText, 'blue')
            result = QMessageBox.warning(self, "Attention", 'The destination directory already exists. ' +
                    'Are you sure you want to replace it?',
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel)
            if (result == QMessageBox.StandardButton.Cancel):
                #  user changed their mind
                logText = 'Download aborted'
                self.updateLog(logText, 'black')

                self.isCopying = False
                self.pbDownload.setText('Start Download')
                return
            else:
                #  user chose to remove
                try:
                    #  try to remove existing directory
                    logText = 'Deleting existing destination directory ' + destDir
                    self.updateLog(logText, 'blue')
                    shutil.rmtree(destDir)

                except Exception as e:
                    #  ran into an error
                    logText = 'Error removing existing destination directory.'
                    self.updateLog(logText, 'red')
                    QMessageBox.critical(self, "Error", "Error remove existing destination directory. " +
                            str(e))
                    logText = 'Download aborted.'
                    self.updateLog(logText, 'red')
                    logText = ('------------------------------------------------------------------------------\n\n')
                    self.updateLog(logText, 'black')

                    self.isCopying = False
                    self.pbDownload.setText('Start Download')
                    return

        #  open and read the CamTrawl metadata file
        try:
            self.metadata.open(sourceDir)
            self.metadata.query()
        except:
            logText = 'Unable to find CamTrawl deployment.'
            self.updateLog(logText, 'red')
            QMessageBox.critical(self, "Error", "Unable to find CamTrawl deployment. Did you " +
                    "select the correct directory?")
            QApplication.restoreOverrideCursor()
            logText = 'Download aborted.'
            self.updateLog(logText, 'red')
            logText = ('------------------------------------------------------------------------------\n\n')
            self.updateLog(logText, 'black')

            self.isCopying = False
            self.pbDownload.setText('Start Download')
            return

        #  get a list of the cameras
        self.cameras = self.metadata.cameras.keys()

        #  create the destination folder structure - we don't create the logs
        #  and settings folders here -we do that below
        try:
            #  if we're copying into a destination folder - create it if needed
            if (self.cbEnableDestFolder.isChecked()):
                destFolder = os.sep.join(destDir.split(os.sep)[:-1])
                if (not os.path.exists(destFolder)):
                    os.mkdir(destFolder)
            #  now make the deployment folder
            os.mkdir(destDir)
            #  and the images folder
            os.mkdir(destDir + os.sep + 'images')
            for cam in self.cameras:
                #  create the camera folders
                os.mkdir(destDir + os.sep + 'images' + os.sep + cam)

            #  create the log file in the destination folder
            log = destDir + os.sep + 'CamtrawlDownloader.log'
            self.logFile = open(log,'w')
            self.logFile.write('--------------------------- CamTrawlDownloader Log ---------------------------\n\n')
            self.logFile.write('Source directory: ' + sourceDir + '\n')
            self.logFile.write('Destination directory: ' + destDir + '\n')
            if doVerify:
                self.logFile.write('Verify after copy: On\n')
            else:
                self.logFile.write('Verify after copy: Off\n')
            self.logFile.write('------------------------------------------------------------------------------\n\n')

        except Exception as e:
            #  there was a problem creating the destination directory structure
            logText = 'Unable to create destination directory!'
            self.updateLog(logText, 'red')
            QMessageBox.critical(self, "Error", "Unable to create destination directory. " +
                    str(e))
            QApplication.restoreOverrideCursor()
            logText = 'Download aborted.'
            self.updateLog(logText, 'red')
            logText = ('------------------------------------------------------------------------------\n\n')
            self.logFile.write(logText)
            self.updateLog(logText, 'black')

            self.isCopying = False
            self.pbDownload.setText('Start Download')
            return

        #  create the copy threads
        self.sourceFiles = {}
        self.workerResults = {}
        self.finishedWorkers = {}
        self.statusWidgets = {}
        self.threads = []
        self.workers = []
        row = 0
        for cam in self.cameras:

            self.sourceFiles[cam] = []
            self.finishedWorkers[cam] = False

            #  construct the source and destination for this camera
            srcPath = sourceDir + os.sep + 'images' + os.sep + cam
            destPath = destDir + os.sep + 'images' + os.sep + cam

            #  generate the file list for this camera
            for i in self.metadata.imageData[cam]:
                self.sourceFiles[cam].append(self.metadata.imageData[cam][i][2] +
                        self.metadata.imageExtension)
            logText = 'Found ' + str(len(self.sourceFiles[cam])) + ' images on camera ' + cam
            self.updateLog(logText, 'black')

            #  add the GUI status elements
            label = QLabel(self.centralwidget)
            label.setMinimumSize(QSize(350, 0))
            self.gridLayout_2.addWidget(label, row, 0, 1, 1)
            progress = QProgressBar(self.centralwidget)
            self.gridLayout_2.addWidget(progress, row, 1, 1, 1)
            self.statusWidgets[cam] = [label, progress]
            row = row + 1

            #  create the thread for this camera
            thisThread = QThread()
            self.threads.append(thisThread)

            #  create the copying worker
            worker = fileCopier.fileCopier(cam, self.sourceFiles[cam], srcPath,
                    destPath, self, verify=doVerify)
            worker.moveToThread(thisThread)
            self.workers.append(worker)

            #  connect the worker's signals/slots
            worker.error.connect(self.workerError)
            worker.progress.connect(self.workerProgress)
            worker.complete.connect(self.workerFinished)
            worker.aborted.connect(self.workerAborted)
            worker.finished.connect(thisThread.quit)
            worker.finished.connect(thisThread.deleteLater)
            thisThread.started.connect(worker.copyFiles)
            thisThread.finished.connect(thisThread.deleteLater)

            #  and finally start the thread
            thisThread.start()

        #  note that we have started
        logText = ('Download started ' + self.startTime.strftime('%Y-%m-%d %H:%M:%S') + '\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'black')

        #  now that the images are being copied, we'll pick up the scraps here.

        #  close the metadata file before copying
        self.metadata.close()

        #  copy the contents of the logs and settings folders
        shutil.copytree(sourceDir + os.sep + 'logs', destDir + os.sep + 'logs')
        shutil.copytree(sourceDir + os.sep + 'settings', destDir + os.sep + 'settings')

        #  set the path to the dest metadata file - we'll use it later
        self.destMetadata = destDir + os.sep + 'logs' + os.sep + 'CamTrawlMetadata.db3'


    def workerError(self, worker, file, error):
        '''
        workerError is called when a worker encounters an error. For the GUI we just
        report all of the errors at the end so we don't do much here.
        '''
        #print(worker + ": " + file + ":::" + error)
        pass


    def workerProgress(self, worker, progress, file):
        '''
        workerProgress updates the GUI with the worker's progress
        '''

        self.statusWidgets[str(worker)][0].setText(file)
        self.statusWidgets[str(worker)][1].setValue(progress)


    def selectDirectory(self):
        '''
        selectDirectory is called when either path selection ("...") button is pressed
        '''

        #  determine which button was pressed
        sender = self.sender()

        #  determine the dialog title based on the button pressed
        if (sender == self.pbSourcePath):
            title = 'Select CamTrawl Deployment Directory'
            defDir = self.sourceDef
        else:
            title = 'Select Destination Directory'
            defDir = self.destDef

        #  present the user with the directory selection dialog
        dirDlg = QFileDialog(self)
        dirName = dirDlg.getExistingDirectory(self, title,
                    defDir, QFileDialog.Option.ShowDirsOnly)
        if (dirName == ''):
            return

        #  set the appropriate text box and update the application settings
        if (sender == self.pbSourcePath):
            idx = self.cbSourcePath.findText(dirName)
            if (idx < 0):
                self.cbSourcePath.insertItem(0, dirName)
                idx = 0
            self.cbSourcePath.setCurrentIndex(idx)
            self.sourceDef = dirName
            self.updateCbPaths(self.cbSourcePath)
        else:
            idx = self.cbDestPath.findText(dirName)
            if (idx < 0):
                self.cbDestPath.insertItem(0, dirName)
                idx = 0
            self.cbDestPath.setCurrentIndex(idx)
            self.destDef = dirName
            self.updateCbPaths(self.cbDestPath)

        #  check if we have both a source and dest
        if ((self.cbSourcePath.currentText != '') and
            (self.cbDestPath.currentText != '')):
            #  we have both a source and dest - enable the download button
            self.pbDownload.setEnabled(True)


    def updateCbPaths(self, cbObject):

        nItems = cbObject.count()
        newList = []

        #  iterate through the items in our combobox
        for i in range(nItems):
            #  get this item from our combobox
            item = cbObject.itemText(i)
            print(item)
            #  clean it up if needed
            item = self.trimDeploymentPath(item)
            print(item)
            #  add this item to our string list - filter out duplicates
            if item not in newList:
                newList.append(item)

        #  update the app settings with our new values
        if (cbObject == self.cbSourcePath):
            self.appSettings.setValue('sourcedir', newList)
        else:
            self.appSettings.setValue('destdir', newList)


    def abortCopy(self):
        '''
        abortCopy is called when either the abort button is pressed or
        the window is closed when copying. It handles the details and
        then signals the threads to quit.
        '''

        #  make sure it makes sense to abort
        if ((self.isAborting) or (not self.isCopying)):
            #  we're already trying to bail or not even copying
            return

        #  warn user that copy is in progress
        result = QMessageBox.warning(self, "Attention", 'The downloader is currently copying files. ' +
                    'Are you sure you want to abort?', QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel)
        if (result == QMessageBox.StandardButton.Cancel):
            #  user changed their mind
            return

        #  user wants to cancel - notify the threads
        self.isAborting = True
        if (self.logFile):
            self.logFile.write('Copy abort requested!')

        self.abort.emit()


    def updateLog(self, text, color):
        '''
        updateLog is called to print text in the GUI text box
        '''

        #  decorate the text and update the textbox
        logText = '<text style="color:' + color +'">' + str(text)
        self.statusText.appendHtml(logText)

        #  ensure that the window is scrolled to see the new line(s) of text.
        self.statusText.verticalScrollBar().setValue(self.statusText.verticalScrollBar().maximum())

        #  force a refresh of the window
        QApplication.processEvents()



    def workerAborted(self, workerName):
        '''
        workerAborted is called by each thread when they are done aborting.
        '''

        #  convert the worker name to a Python string
        workerName = str(workerName)

        #  serialize access to self.finishedWorkers and the "all done" check.
        #  We need to do this because it would be possible to deadlock here
        #  if there is a context switch when one thread is in the middle of
        #  the check and the other finishes. The first thread may have a stale
        #  copy of self.finishedWorkers and would not evaluate allDone correctly
        #  evaluating as false even though the last thread finished.
        self.mutex.lock()

        #  set this worker's state as finished
        self.finishedWorkers[workerName] = True

        #  check if all workers are done
        allDone = True
        for worker in self.finishedWorkers:
            allDone &= self.finishedWorkers[worker]

        #  unlock our mutex
        self.mutex.unlock()

        #  check if all of the threads have aborted
        if (not allDone):
            return

        #  all threads aborted - clean up the GUI
        for cam in self.cameras:
            #  remove our worker status widgets
            self.statusWidgets[cam][0].hide()
            self.statusWidgets[cam][1].hide()
            self.gridLayout_2.removeWidget(self.statusWidgets[cam][0])
            self.gridLayout_2.removeWidget(self.statusWidgets[cam][1])

        #  log the abort
        endTime = datetime.datetime.now()
        logText = ('Download aborted ' + endTime.strftime('%Y-%m-%d %H:%M:%S') + '\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'red')

        logText = ('------------------------------------------------------------------------------\n\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'black')

        #  close the log file
        if (self.logFile):
            self.logFile.close()
        self.logFile = None

        #  reset the UI
        self.pbDownload.setText('Start Download')
        self.isCopying = False
        self.isAborting = False
        self.statusWidgets = []

        #  emit the finished signal to notify the copier threads they're done
        self.finished.emit()

        #  if we aborted because the window was closed...
        if (self.isClosing):
            #  close the application
            self.close()


    def workerFinished(self, workerName, nCopied, copiedFiles, nErrored, errorFiles):
        '''
        workerFinished is called by each thread when they finish up. Finishing happens
        when they work through their file lis.
        '''

        #  convert the worker name to a Python string
        workerName = str(workerName)
        #print("workerFinished: " + workerName)

        #  serialize access to self.finishedWorkers and the "all done" check.
        self.mutex.lock()

        #  set this worker's state as finished
        self.finishedWorkers[workerName] = True
        #print("set worker finished")

        #  store the results
        self.workerResults[workerName] = {'nCopied':nCopied, 'copiedFiles':copiedFiles,
                'nErrors':nErrored, 'errorFiles':errorFiles}
        #print("stored the results")

        #  check if all workers are done
        allDone = True
        for worker in self.finishedWorkers:
            allDone &= self.finishedWorkers[worker]

        #print("setting alldone: " + str(allDone))

        #  unlock our mutex
        self.mutex.unlock()
        #print("Unlocked")

        #  check if we're all done - if not just return
        if (not allDone):
            return

        #  all workers are done
        endTime = datetime.datetime.now()
        duration = endTime - self.startTime
        logText = ('Download finished ' + endTime.strftime('%Y-%m-%d %H:%M:%S') + ' elapsed time: ' +
                str(duration) + '\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'black')

        #  update the GUI and report the results
        for cam in self.cameras:

            #  remove our worker status widgets
            self.statusWidgets[cam][0].hide()
            self.statusWidgets[cam][1].hide()
            self.gridLayout_2.removeWidget(self.statusWidgets[cam][0])
            self.gridLayout_2.removeWidget(self.statusWidgets[cam][1])

            #  report results
            nSourceFiles = len(self.sourceFiles[cam])
            nCopied = self.workerResults[cam]['nCopied']
            nErrored = self.workerResults[cam]['nErrors']
            logText = ('Worker ' + cam + ' copied ' + str(nCopied) + ' of ' +
                        str(nSourceFiles) + ' files.\n')
            self.logFile.write(logText)

            #  check if we ran into any problems
            if (nSourceFiles != nCopied):
                #  Yes, we had errors splash the results in red on the screen
                if (nErrored == 1):
                    s = ' file was '
                else:
                    s = ' files were '
                logText = ('ERROR: ' + str(nErrored) + s + 'not copied!:\n')
                self.updateLog(logText, 'red')
                for i in range(nErrored):
                    logText = (errorFiles['errorFiles'][i] + ':::' + errorFiles['error'][i] + '\n')
                    self.updateLog(logText, 'red')
            else:
                #  copy ok - splash results in green
                self.updateLog(logText, 'green')

        #  if checksums were generated - update the destination metadata file
        if (self.cbVerify.isChecked()):
            self.updateMetadataHashes(self.destMetadata, self.cameras, self.workerResults)

        #  we're done for the most part - update the GUI
        logText = ('Download finished.\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'black')
        logText = ('------------------------------------------------------------------------------\n\n')
        self.logFile.write(logText)
        self.updateLog(logText, 'black')

        #  report the erros at the top so they are easy to find
        for cam in self.cameras:
            logText = ('------------------------------------------------------------------------------\n\n')
            self.logFile.write(logText)
            logText = (str(self.workerResults[cam]['nErrors']) +
                    ' error(s) encountered for camera ' + cam + '\n')
            self.logFile.write(logText)
            logText = ('------------------------------------------------------------------------------\n\n')
            self.logFile.write(logText)
            if (self.workerResults[cam]['nErrors'] > 0):
                for i in range(self.workerResults[cam]['nErrors']):
                    logText = (self.workerResults[cam]['errorFiles']['fileList'][i] +
                            ':::' + self.workerResults[cam]['errorFiles']['error'][i] + '\n')
                    self.logFile.write(logText)
            else:
                logText = ('None\n')
                self.logFile.write(logText)
            logText = ('\n')
            self.logFile.write(logText)

        #  report the full results to file here
        for cam in self.cameras:
            logText = ('------------------------------------------------------------------------------\n\n')
            self.logFile.write(logText)
            logText = (str(self.workerResults[cam]['nCopied']) +
                    ' files copied successfully for camera ' + cam + '\n')
            self.logFile.write(logText)
            logText = ('------------------------------------------------------------------------------\n\n')
            self.logFile.write(logText)
            for i in range(self.workerResults[cam]['nCopied']):
                logText = (self.workerResults[cam]['copiedFiles']['fileList'][i] +
                        ':::' + self.workerResults[cam]['copiedFiles']['hash'][i] + '\n')
                self.logFile.write(logText)

        #  close the log file
        if (self.logFile):
            self.logFile.close()
        self.logFile = None

        #  reset the UI
        self.pbDownload.setText('Start Download')
        self.isCopying = False
        self.isAborting = False
        self.statusWidgets = []

        #  emit the finished signal to notify the copier threads they're done
        self.finished.emit()


    def updateMetadataHashes(self, metadataFile, cameras, results):
        '''
        updateMetadataHashes inserts the file checksums into the metadata images table.
        '''

        db = QSqlDatabase.addDatabase("QSQLITE", 'downloadUpdate')
        db.setDatabaseName(metadataFile)
        if not db.open():
            QMessageBox.warning(self, "Warning", "Say what? Unable to open up Camtrawl metadata database " +
                    "file for update. That's unpossible!")
            logText = ('Unable to open metadata database file ' + metadataFile + " for update. \n" +
                    "This is not a critical error but you should verify that the file copied correctly " +
                    "and copy it manually if it did not.")
            self.updateLog(logText, 'red')
            self.logFile.write(logText)

        #  create a query object
        dbQuery = QSqlQuery(db)

        #  create a progress bar for this long running event
        label = QLabel(self.centralwidget)
        label.setMinimumSize(QSize(350, 0))
        self.gridLayout_2.addWidget(label, 0, 0, 1, 1)
        progress = QProgressBar(self.centralwidget)
        self.gridLayout_2.addWidget(progress, 0, 1, 1, 1)

        #  iterate thru the cameras and copied images and update the checksum
        for cam in cameras:
            #  use a transaction due to the large number of updates
            dbQuery.exec("BEGIN TRANSACTION")

            #  update the log
            logText = ('Updating checksums in metadata database for camera ' + cam + ' (This can take a while...)\n')
            self.logFile.write(logText)
            self.updateLog(logText, 'black')

            #  set the status label
            label.setText("Updating metadata: " + cam)

            #  iterate thru the "good" images
            nImages =results[cam]['nCopied']
            for i in range(nImages):
                pct = int(round((i / float(nImages)) * 100.))
                progress.setValue(pct)
                QApplication.processEvents()
                imageName = os.path.splitext(results[cam]['copiedFiles']['fileList'][i])[0]
                checksum = results[cam]['copiedFiles']['hash'][i]
                sql = ("UPDATE images SET md5_checksum= '" + checksum + "' " +
                        "WHERE camera='" + cam + "' AND name='" + imageName + "'")
                query = QSqlQuery(sql, db)
                query.exec()

            #  end our transaction
            dbQuery.exec("END TRANSACTION")

        #  remove our progress bar
        progress.hide()
        label.hide()
        self.gridLayout_2.removeWidget(progress)
        self.gridLayout_2.removeWidget(label)

        #  close the database
        db.close()

        #  and remove the connection
        QSqlDatabase.removeDatabase('downloadUpdate')


    def enableSubdirClicked(self, state):
        '''
        enableSubdirClicked is called when the enable checkbox next to the subdir
        text edit is clicked. It enables/disables the text box according to the
        check state
        '''

        self.destFolder.setEnabled(state)


    def cbIndexChanged(self, index):
        '''
        cbIndexChanged is called when either one of the combo boxes is changed
        it simply updates the default path provided to the directory selection
        dialog.
        '''

        #  get the sender
        sender = self.sender()

        #  get the sender's text
        text = sender.itemText(index)

        #  trim off the deployment dir (if any)
        text = self.trimDeploymentPath(text)

        #  set the default for the selection dialog
        if (sender == self.cbSourcePath):
            #  this is the cbsourcePath widget
            self.sourceDef = text
        else:
            #  this is the cbDestPath widget
            self.destDef = text


    def trimDeploymentPath(self, path):
        '''
        trimDeploymentPath simply lops off the deployment directory making some
        big assumptions. We store the parent of the source deployment directory
        just to make selections easier.
        '''

        #  check if we seem to have a camtrawl deployment directory
        if ((path.find('D20') > -1) and (path.find('-T') > -1)):
            #  assume the deployment dir is the last in the path and remove
            path = path.split('/')
            path = '/'.join(path[:-1])

        return path


    def closeEvent(self, event):
        '''
        closeEvent is called when the GUI is closed.
        '''

        #  if we're copying, check if we should abort
        if (self.isCopying):
            #  abort
            self.abortCopy()

            #  set the isClosing variable so we know we should close
            #  after the threads terminate.
            self.isClosing = True

            #  since we have to wait for the threads to finish, we ignore
            #  and return for now.
            event.ignore()
            return

        #  save the application state
        self.appSettings.setValue('winposition', self.pos())
        self.appSettings.setValue('winsize', self.size())
        self.appSettings.setValue('verify', self.cbVerify.isChecked())
        self.appSettings.setValue('enabledestfolder', self.cbEnableDestFolder.isChecked())
        self.appSettings.setValue('destfolder', self.destFolder.text())
        self.updateCbPaths(self.cbSourcePath)
        self.appSettings.setValue('sourceindex', self.cbSourcePath.currentIndex())
        self.updateCbPaths(self.cbDestPath)
        self.appSettings.setValue('destindex', self.cbDestPath.currentIndex())

        event.accept()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    form = CamtrawlDownloader()
    form.show()
    app.exec()
