import ctypes
import os
import fcntl
class AtaCmd(ctypes.Structure):
  """ATA Command Pass-Through
     http://www.t10.org/ftp/t10/document.04/04-262r8.pdf"""




  _fields_ = [
      ('opcode', ctypes.c_ubyte),
      ('protocol', ctypes.c_ubyte),
      ('flags', ctypes.c_ubyte),
      ('features', ctypes.c_ubyte),
      ('sector_count', ctypes.c_ubyte),
      ('lba_low', ctypes.c_ubyte),
      ('lba_mid', ctypes.c_ubyte),
      ('lba_high', ctypes.c_ubyte),
      ('device', ctypes.c_ubyte),
      ('command', ctypes.c_ubyte),
      ('reserved', ctypes.c_ubyte),
      ('control', ctypes.c_ubyte) ]


class SgioHdr(ctypes.Structure):
  """<scsi/sg.h> sg_io_hdr_t."""

  _fields_ = [
      ('interface_id', ctypes.c_int),
      ('dxfer_direction', ctypes.c_int), #SG_DXFER_NONE SG_DXFER_TO_DEV SG_DXFER_FROM_DEV  SG_DXFER_TO_FROM_DEV  SG_DXFER_UNKNOWN
      ('cmd_len', ctypes.c_ubyte),
      ('mx_sb_len', ctypes.c_ubyte), #maximum size that can be written to the sbp  when a sense_buffer is output which is usually in an error situation
      ('iovec_count', ctypes.c_ushort),
      ('dxfer_len', ctypes.c_uint), #This is the number of bytes to be moved in the data transfer associated with the command
      ('dxferp', ctypes.c_void_p), #>= dxfer_len size.data will be transferred to or from this buffer
      ('cmdp', ctypes.c_void_p), # points to the SCSI command to be executed. 
      ('sbp', ctypes.c_void_p), #Most successful commands do not output a sense buffer and this will be indicated by 'sb_len_wr' being zero
      ('timeout', ctypes.c_uint),
      ('flags', ctypes.c_uint),
      ('pack_id', ctypes.c_int),
      ('usr_ptr', ctypes.c_void_p),
      ('status', ctypes.c_ubyte),
      ('masked_status', ctypes.c_ubyte), #masked_status == ((status & 0x3e) >> 1) . So 'masked_status' strips the vendor information bits off 'status' and then shifts it right one position
      ('msg_status', ctypes.c_ubyte),
      ('sb_len_wr', ctypes.c_ubyte), #This is the actual number of bytes written to the user memory pointed to by sbp
      ('host_status', ctypes.c_ushort),
      ('driver_status', ctypes.c_ushort),
      ('resid', ctypes.c_int),
      ('duration', ctypes.c_uint),
      ('info', ctypes.c_uint)] #This value is designed to convey useful information back to the user about the associated request

def SwapString(str):
  """Swap 16 bit words within a string.

  String data from an ATA IDENTIFY appears byteswapped, even on little-endian
  achitectures. I don't know why. Other disk utilities I've looked at also
  byte-swap strings, and contain comments that this needs to be done on all
  platforms not just big-endian ones. So... yeah.
  """
  s = []
  for x in range(0, len(str) - 1, 2):
    s.append(str[x+1])
    s.append(str[x])
  return ''.join(s).strip()

def GetDriveIdSgIo(dev,data):
  """Return information from interrogating the drive.

  This routine issues a SG_IO ioctl to a block device, which
  requires either root privileges or the CAP_SYS_RAWIO capability.

  Args:
    dev: name of the device, such as 'sda' or '/dev/sda'

  Returns:
    (serial_number, fw_version, model) as strings
  """

  if dev[0] != '/':
    dev = '/dev/' + dev
  ata_cmd = AtaCmd(opcode=data['opcode'],  # ATA PASS-THROUGH (12)
                   protocol=data['protocol'],  # PIO Data-In
                  # flags field
                   # OFF_LINE = 0 (0 seconds offline)
                   # CK_COND = 1 (copy sense data in response)
                   # T_DIR = 1 (transfer from the ATA device)
                   # BYT_BLOK = 1 (length is in blocks, not bytes)
                   # T_LENGTH = 2 (transfer length in the SECTOR_COUNT field)
                   flags=data['flags'],
                   features=data['features'], sector_count=data['sector_count'],
                   lba_low=data['lba_low'], lba_mid=data['lba_mid'], lba_high=data['lba_high'],
                   device=data['device'],
                   command=data['command'],  # IDENTIFY
                   reserved=data['reserved'], control=data['control'])
  ASCII_S = 83
  SG_DXFER_FROM_DEV = -3
  sense = ctypes.c_buffer(64)
  identify = ctypes.c_buffer(512)
  sgio = SgioHdr(interface_id=ASCII_S, dxfer_direction=SG_DXFER_FROM_DEV,
                 cmd_len=ctypes.sizeof(ata_cmd),
                 mx_sb_len=ctypes.sizeof(sense), iovec_count=0,
                 dxfer_len=ctypes.sizeof(identify),
                 dxferp=ctypes.cast(identify, ctypes.c_void_p),
                 cmdp=ctypes.addressof(ata_cmd),
                 sbp=ctypes.cast(sense, ctypes.c_void_p), timeout=3000,
                 flags=0, pack_id=0, usr_ptr=None, status=0, masked_status=0,
                 msg_status=0, sb_len_wr=0, host_status=0, driver_status=0,
                 resid=0, duration=0, info=0)
  SG_IO = 0x2285  # <scsi/sg.h>
  # print ctypes.addressof(sgio)
  libc=ctypes.CDLL('libc.so.6')
  fd=os.open(dev,os.O_RDWR,0666)
  value=ctypes.c_uint64(ctypes.addressof(sgio))
  if libc.ioctl(fd,SG_IO,value) != 0:
      print "fcntl failed"
      return None
  if ord(sense[0]) == 0x72:
      print 'Response code: ', hex(ord(sense[0])), 'Sense key: ' , hex(ord(sense[1]) & 0x0f) , " ASC: " , hex(ord(sense[2])), " ASCQ: " , hex(ord(sense[3]))
  else:
      print 'Response code: ', hex(ord(sense[0])), 'Sense key: ' , hex(ord(sense[2]) & 0x0f) , " ASC: " , hex(ord(sense[12])), " ASCQ: " , hex(ord(sense[13]))
  #    return None
  # IDENTIFY format as defined on pg 91 of
  # http://t13.org/Documents/UploadedDocuments/docs2006/D1699r3f-ATA8-ACS.pdf
  serial_no = SwapString(identify[20:40])
  fw_rev = SwapString(identify[46:54])
  model = SwapString(identify[54:93])
  os.close(fd)
  return (serial_no, fw_rev, model)



def ReadBlockSgIo(dev,data):
  if dev[0] != '/':
    dev = '/dev/' + dev
  #ata_cmd = AtaCmd(opcode=0xa1,  # ATA PASS-THROUGH (12)
   #                protocol=6<<1,  # PIO Data-In
                   # flags field
                   # OFF_LINE = 0 (0 seconds offline)
                   # CK_COND = 1 (copy sense data in response)
                   # T_DIR = 1 (transfer from the ATA device)
                   # BYT_BLOK = 1 (length is in blocks, not bytes)
                   # T_LENGTH = 2 (transfer length in the SECTOR_COUNT field)
    #               flags=0x2e,
     #              features=0, sector_count=n_blocks,
      #             lba_low=lba, lba_mid=(lba >> 8), lba_high=(lba >>16),
       #            device=0x40,
        #           command=0x25,  # IDENTIFY
         #          reserved=0, control=0)
  ata_cmd = AtaCmd(opcode=data['opcode'],  # ATA PASS-THROUGH (12)
                   protocol=data['protocol'],  # PIO Data-In
                   # flags field
                   # OFF_LINE = 0 (0 seconds offline)
                   # CK_COND = 1 (copy sense data in response)
                   # T_DIR = 1 (transfer from the ATA device)
                   # BYT_BLOK = 1 (length is in blocks, not bytes)
                   # T_LENGTH = 2 (transfer length in the SECTOR_COUNT field)
                   flags=data['flags'],
                   features=data['features'], sector_count=data['sector_count'],
                   lba_low=data['lba_low'], lba_mid=data['lba_mid'], lba_high=data['lba_high'],
                   device=data['device'],
                   command=data['command'],  # IDENTIFY
                   reserved=data['reserved'], control=data['control'])

  ASCII_S = 83
  SG_DXFER_FROM_DEV = -3
  sense = ctypes.c_buffer(64)
  identify = ctypes.c_buffer(512*data['sector_count'])
  sgio = SgioHdr(interface_id=ASCII_S, dxfer_direction=SG_DXFER_FROM_DEV,
                 cmd_len=ctypes.sizeof(ata_cmd),
                 mx_sb_len=ctypes.sizeof(sense), iovec_count=0,
                 dxfer_len=ctypes.sizeof(identify),
                 dxferp=ctypes.cast(identify, ctypes.c_void_p),
                 cmdp=ctypes.addressof(ata_cmd),
                 sbp=ctypes.cast(sense, ctypes.c_void_p), timeout=3000,
                 flags=0, pack_id=0, usr_ptr=None, status=0, masked_status=0,
                 msg_status=0, sb_len_wr=0, host_status=0, driver_status=0,
                 resid=0, duration=0, info=0)
  SG_IO = 0x2285  # <scsi/sg.h>
  libc=ctypes.CDLL('libc.so.6')
  fd=os.open(dev,os.O_RDWR,0666)
  value=ctypes.c_uint64(ctypes.addressof(sgio))
  if libc.ioctl(fd,SG_IO,value) != 0:
      print "fcntl failed"
      return None
  if ord(sense[0]) == 0x72:
      print 'Response code: ', hex(ord(sense[0])), 'Sense key: ' , hex(ord(sense[1]) & 0x0f) , " ASC: " , hex(ord(sense[2])), " ASCQ: " , hex(ord(sense[3]))
  else:
      print 'Response code: ', hex(ord(sense[0])), 'Sense key: ' , hex(ord(sense[2]) & 0x0f) , " ASC: " , hex(ord(sense[12])), " ASCQ: " , hex(ord(sense[13]))

 # print "res: ", SwapString(identify[:])
  return 


#serial_no,fw_rev,model=GetDriveIdSgIo("/dev/sda")
#print "serial number: ", serial_no
#print "firmware revision: ", fw_rev
#print "model: " ,model
#print "--- after ---"
#ReadBlockSgIo("/dev/sda",1,1)
