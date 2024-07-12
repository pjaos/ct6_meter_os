
import uos

class VFS():

    @staticmethod
    def GetFSInfo():
        """@brief Get the used and available disk space.
           @return A tuple containing
                   0 = The total disk space in bytes.
                   1 = The used disk space in bytes.
                   2 = The % used disk space."""
        stats = uos.statvfs("/")
        if stats and len(stats) == 10:
            f_bsize  = stats[0] # The file system block size in bytes
#            f_frsize = stats[1] # The fragment size in bytes
            f_blocks = stats[2] # The size of fs in f_frsize units
            f_bfree  = stats[3] # The number of free blocks
#            f_bavail = stats[4] # The number of free blocks for unprivileged users
#            f_files  = stats[5] # The number of inodes
#            f_ffree  = stats[6] # The number of free inodes
#            f_favail = stats[7] # The number of free inodes for unprivileged users
#            f_fsid   = stats[8] # The file system ID
#            f_flags = stats[0]  # The mount flags

            totalBytes = f_bsize * f_blocks
            freeSpace  = f_bsize * f_bfree
            usedSpace  = totalBytes - freeSpace

            if usedSpace > 0:
                percentageUsed = (usedSpace / totalBytes) * 100.0
            else:
                percentageUsed = 0.0

            return (totalBytes, usedSpace, percentageUsed)

        raise Exception("GetFSInfo(): {} is invalid.".format(stats))


    @staticmethod
    def ShowFSInfo(uo):
        """@brief Show the file system info.
           @param A UO instance or None"""
        if uo:
            totalBytes, usedSpace, percentageUsed = VFS.GetFSInfo()
            uo.info("File system information.")
            uo.info("Total Space (MB): {:.2f}".format(totalBytes/1E6))
            uo.info("Used Space (MB):  {:.2f}".format(usedSpace/1E6))
            uo.info("Used Space (%):   {:.1f}".format(percentageUsed))


