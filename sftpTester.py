
import sftpCopier
from PyQt6 import QtCore

class sftpTester(QtCore.QObject):

    def __init__(self):

        super(sftpTester, self).__init__()

        self.copier = sftpCopier.sftpCopier('Test', self)

        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.startTest)
        timer.setSingleShot(True)
        timer.start(1)


    def startTest(self):

        ip = '192.168.0.149'
        user = 'camtrawl'
        password = 'pollock'


        #  open the connection
        try:
            self.copier.connect(ip, user, password)
        except Exception as err:
            print("ooops, we couldn't open up a connection!")
            print(err)
            QtCore.QCoreApplication.instance().quit()

        self.copier.getDeployments()

        #  close the connection
        self.copier.disconnect()

        #  quit
        QtCore.QCoreApplication.instance().quit()



#  this is a common way to make a script with classes/functions in it run
if __name__ == "__main__":
    import sys
    app = QtCore.QCoreApplication(sys.argv)
    form = sftpTester()
    sys.exit(app.exec())






