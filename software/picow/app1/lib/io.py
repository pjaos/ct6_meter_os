# Helper methods for IO functionality

import os

class IO(object):
    
    TYPE_DIR            = 0x4000
    TYPE_FILE           = 0x8000

    @staticmethod
    def DirExists(aPath):
        """@param aPath The path to check.
           @return True if the dir exists."""
        try:
            return (os.stat(aPath)[0] & IO.TYPE_DIR) != 0
        except OSError:
            return False
            
    @staticmethod
    def FileExists(filename):
        """@param filename The file to check.
           @return True if the filename exists."""
        try:
            return (os.stat(filename)[0] & IO.TYPE_DIR) == 0
        except OSError:
            return False