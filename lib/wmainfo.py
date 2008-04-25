# Description:
# wmainfo-py gives you access to low level information on wma files.
# * It identifies all "ASF_..." objects and shows each objects size
# * It returns info such as bitrate, size, length, creation date etc
# * It returns meta-tags from ASF_Content_Description_Object
#
# Note:
# I wrestled with the ASF spec (150 page .doc format!) with no joy for
# a while, then found Dan Sully's Audio-WMA Perl module:
# (http://cpants.perl.org/dist/Audio-WMA :: http://www.slimdevices.com/)
# This entire library is essentially a translation of parts of WMA.pm
# to Python. All credit for the hard work is owed to Dan...
#
# License:: Artistic/Perl
# Author:: Darren Kirby (mailto:bulliver@badcomputer.org)
# Website:: http://badcomputer.org/unix/code/wmainfo//

from os import stat
from struct import unpack
import time, re

class WmaInfoError:
    def __init__(self, error):
        self.error = error
    def __str__(self):
        return self.error

class WmaInfo:
    def __init__(self, file, debug=None):
        # 'public' attributes
        self.drm = None         # boolean
        self.tags = {}          # hash
        self.headerObject = {}  # hash of arrays
        self.info = {}          # hash

        self.file = file
        self.debug = debug
        self.__parseWmaHeader()

    def printobjects(self):
        '''
         ASF_Header_Object prints: "name: GUID size num_objects"
         All other objects print: "name: GUID size offset"
        '''
        for key,val in self.headerObject.iteritems():
            print "%s: %s %i %i" % (key, val[0], val[1], val[2])

    def hasdrm(self):
        '''
        Returns true if the file has DRM, ie: if a
        *Content_Encryption_Object is present
        '''
        if self.drm:
            return True
        else:
            return False

    def printtags(self):
        '''
        This is all the 'id3' like info gathered from:
        ASF_Content_Description_Object and
        ASF_Extended_Content_Description_Object
        '''
        for k,v in self.tags.iteritems(): 
            print "%s:%s%s" % (k, " " * (13 - len(k)), v)

    def hastag(self, tag):
        '''returns true if tags[tag] has a value'''
        if self.tags.has_key(tag) and self.tags[tag] != "":
            return True
        else:
            return False

    def printinfo(self):
        '''
        This is all the 'non-id3' like info gathered from
        ASF_File_Properties_Object and
        ASF_Extended_Content_Description_Object
        '''
        for k,v in self.info.iteritems():
            print "%s:%s%s" % (k, " " * (20 - len(k)), v)

    def hasinfo(self, field):
        '''Returns true if info[field] has a value'''
        if self.info.has_key(field) and self.tags[tag] != "":
            return True
        else:
            return False

    def parsestream(self):
        '''
        I don't think most people will want/need this info
        so it is not parsed automatically
        '''
        self.stream = {}
        try:
            offset = int(self.headerObject['ASF_Stream_Properties_Object'][2])
            self.__parseASFStreamPropertiesObject(offset)
        except:
            raise WmaInfoError("Cannot grok ASF_Stream_Properties_Object")

    def __parseWmaHeader(self):
        self.size = int(stat(self.file)[6])
        self.fh = open(self.file, "rb")
        self.offset = 0
        self.fileOffset = 30
        self.guidMapping = self.__knownGUIDs()
        self.reverseGuidMapping = {}
        for k,v in self.guidMapping.iteritems():
            self.reverseGuidMapping[v] = k

        try:
            objectId      = self.__byteStringToGUID(self.fh.read(16))
            objectSize    = unpack("<2L", self.fh.read(8))[0]
            headerObjects = unpack("<1L", self.fh.read(4))[0]
            reserved1     = unpack("b", self.fh.read(1))[0]
            reserved2     = unpack("b", self.fh.read(1))[0]
            objectIdName  = self.reverseGuidMapping[objectId]
        except:
            raise WmaInfoError(self.file + " doesn't appear to have a valid ASF header")

        if objectSize > self.size:
            raise WmaInfoError("Header size reported larger than file size")

        self.headerObject[objectIdName] = [objectId,  objectSize, headerObjects, reserved1, reserved2]

        if self.debug:
            print "objectId:      %s" % objectId
            print "objectIdName:  %s" % self.reverseGuidMapping[objectId]
            print "objectSize:    %s" % objectSize
            print "headerObjects: %s" % headerObjects
            print "reserved1:     %s" % reserved1
            print "reserved2:     %s" % reserved2

        self.headerData = self.fh.read(objectSize - 30)
        self.fh.close # Done with the file before we get going

        for n in range(headerObjects):
            nextObject     = self.__readAndIncrementOffset(16)
            nextObjectText = self.__byteStringToGUID(nextObject)
            nextObjectSize = self.__parse64BitString(self.__readAndIncrementOffset(8))
            nextObjectName = self.reverseGuidMapping[nextObjectText]

            self.headerObject[nextObjectName] = [nextObjectText, nextObjectSize, self.fileOffset]
            self.fileOffset += nextObjectSize

            if self.debug:
                print "nextObjectGUID: %s" % nextObjectText
                print "nextObjectName: %s" % nextObjectName
                print "nextObjectSize: %s" % nextObjectSize

            # start looking at object contents
            if (nextObjectName == 'ASF_File_Properties_Object'):
                self.__parseASFFilePropertiesObject()
                continue
            elif (nextObjectName == 'ASF_Content_Description_Object'):
                self.__parseASFContentDescriptionObject()
                continue
            elif (nextObjectName == 'ASF_Extended_Content_Description_Object'):
                self.__parseASFExtendedContentDescriptionObject()
                continue
            elif (nextObjectName == 'ASF_Content_Encryption_Object') or (nextObjectName == 'ASF_Extended_Content_Encryption_Object'):
                self.drm = 1

            # set our next object size
            self.offset += nextObjectSize - 24

    def __parseASFFilePropertiesObject(self):
        fileid                          = self.__readAndIncrementOffset(16)
        self.info['fileid_guid']        = self.__byteStringToGUID(fileid)
        self.info['filesize']           = int(self.__parse64BitString(self.__readAndIncrementOffset(8)))
        self.info['creation_date']      = unpack("<Q", self.__readAndIncrementOffset(8))[0]
        self.info['creation_date_unix'] = self.__fileTimeToUnixTime(self.info['creation_date'])
        self.info['creation_string']    = time.strftime("%c", time.gmtime(self.info['creation_date_unix']))
        self.info['data_packets']       = unpack("<4H", self.__readAndIncrementOffset(8))[0]
        self.info['play_duration']      = self.__parse64BitString(self.__readAndIncrementOffset(8))
        self.info['send_duration']      = self.__parse64BitString(self.__readAndIncrementOffset(8))
        self.info['preroll']            = unpack("<4H", self.__readAndIncrementOffset(8))[0]
        self.info['playtime_seconds']   = int(self.info['play_duration'] / 10000000 - self.info['preroll'] / 1000)
        flags_raw                       = unpack("<L", self.__readAndIncrementOffset(4))[0]
        if (flags_raw & 0x0001) == False:
            self.info['broadcast'] = 0
        else:
            self.info['broadcast'] = 1
        if (flags_raw & 0x0002) == False:
            self.info['seekable'] = 0
        else:
            self.info['seekable'] = 1
        self.info['min_packet_size']    = unpack("<2H", self.__readAndIncrementOffset(4))[0]
        self.info['max_packet_size']    = unpack("<2H", self.__readAndIncrementOffset(4))[0]
        self.info['max_bitrate']        = unpack("<2H", self.__readAndIncrementOffset(4))[0]
        self.info['bitrate']            = self.info['max_bitrate'] / 1000

        if self.debug:
            for key,val in self.info.iteritems():
                print "%s: %s" % (key, val)

    def __parseASFContentDescriptionObject(self):
        lengths = {}
        keys = ["Title", "Author", "Copyright", "Description", "Rating"]
        for key in keys:  # read the lengths of each key
            lengths[key] = unpack("H", self.__readAndIncrementOffset(2))[0]
        for key in keys:  # now pull the data based on length
            self.tags[key] = self.__decodeBinaryString(self.__readAndIncrementOffset(lengths[key]))

    def __parseASFExtendedContentDescriptionObject(self):
        ext_info = {}
        ext_info['content_count'] = unpack("H", self.__readAndIncrementOffset(2))[0]
        for n in range(ext_info['content_count']):
            ext = {}
            ext['base_offset']  = self.offset + 30
            ext['name_length']  = unpack("H", self.__readAndIncrementOffset(2))[0]
            ext['name']         = self.__decodeBinaryString(self.__readAndIncrementOffset(ext['name_length']))
            ext['value_type']   = unpack("H", self.__readAndIncrementOffset(2))[0]
            ext['value_length'] = unpack("H", self.__readAndIncrementOffset(2))[0]

            value = self.__readAndIncrementOffset(ext['value_length'])
            if ext['value_type'] <= 1:
                ext['value'] = self.__decodeBinaryString(value)
            elif ext['value_type'] == 4:
                ext['value'] = self.__parse64BitString(value)
            else:
                valTypeTemplates = ["", "", "<2H", "<2H", "", "H"]
                ext['value'] = unpack(valTypeTemplates[ext['value_type']], value)[0]

            if self.debug:
                print "base_offset:  %i" % ext['base_offset']
                print "name length:  %i" % ext['name_length']
                print "name:         %s" % ext['name']
                print "value type:   %i" % ext['value_type']
                print "value length: %i" % ext['value_length']
                print "value:        %s" % ext['value']

            ext_info[ext['name']] = ext['value']

        # Sort and dispatch info
        strMatch = re.compile("(TrackNumber|AlbumTitle|AlbumArtist|Genre|Year|Composer|Mood|Lyrics|BeatsPerMinute)")
        for k,v in ext_info.iteritems():
            if strMatch.search(k) != None:
                self.tags[k.replace("WM/", "")] = v # dump "WM/"
            else:
                self.info[k.replace("WM/", "")] = v

    def __parseASFStreamPropertiesObject(self, offset):
        self.offset = offset - 6 # gained an extra 6 bytes somewhere?!

        streamType                        = self.__readAndIncrementOffset(16)
        self.stream['stream_type_guid']   = self.__byteStringToGUID(streamType)
        self.stream['stream_type_name']   = self.reverseGuidMapping[self.stream['stream_type_guid']]
        errorType                         = self.__readAndIncrementOffset(16)
        self.stream['error_correct_guid'] = self.__byteStringToGUID(errorType)
        self.stream['error_correct_name'] = self.reverseGuidMapping[self.stream['error_correct_guid']]

        self.stream['time_offset']        = unpack('4H', self.__readAndIncrementOffset(8))[0]
        self.stream['type_data_length']   = unpack('2H', self.__readAndIncrementOffset(4))[0]
        self.stream['error_data_length']  = unpack('2H', self.__readAndIncrementOffset(4))[0]
        flags_raw                         = unpack('H', self.__readAndIncrementOffset(2))[0]
        self.stream['stream_number']      = flags_raw & 0x007F
        self.stream['encrypted']          = flags_raw & 0x8000

        #  reserved - set to zero
        self.__readAndIncrementOffset(4)

        self.stream['type_specific_data'] = self.__readAndIncrementOffset(self.stream['type_data_length'])
        self.stream['error_correct_data'] = self.__readAndIncrementOffset(self.stream['error_data_length'])

        if (self.stream['stream_type_name'] == 'ASF_Audio_Media'):
            self.__parseASFAudioMediaObject()

    def __parseASFAudioMediaObject(self):
        data = self.stream['type_specific_data'][0:16]
        self.stream['audio_channels']        = unpack('H', data[2:4])[0]
        self.stream['audio_sample_rate']     = unpack('2H', data[4:8])[0]
        self.stream['audio_bitrate']         = unpack('2H', data[8:12])[0] * 8
        self.stream['audio_bits_per_sample'] = unpack('H', data[14:16])[0]

    def __decodeBinaryString(self, data):
        textString = data.decode('utf-16le','ignore')[0:-1]
        return textString

    def __readAndIncrementOffset(self, size):
        value = self.headerData[self.offset:(self.offset + size)]
        self.offset += size
        return value

    def __byteStringToGUID(self, byteString):
        byteString = unpack("16B" , byteString)
        guidString  = "%02X" % byteString[3]
        guidString += "%02X" % byteString[2]
        guidString += "%02X" % byteString[1]
        guidString += "%02X" % byteString[0]
        guidString += '-'
        guidString += "%02X" % byteString[5]
        guidString += "%02X" % byteString[4]
        guidString += '-'
        guidString += "%02X" % byteString[7]
        guidString += "%02X" % byteString[6]
        guidString += '-'
        guidString += "%02X" % byteString[8]
        guidString += "%02X" % byteString[9]
        guidString += '-'
        guidString += "%02X" % byteString[10]
        guidString += "%02X" % byteString[11]
        guidString += "%02X" % byteString[12]
        guidString += "%02X" % byteString[13]
        guidString += "%02X" % byteString[14]
        guidString += "%02X" % byteString[15]
        return guidString

    def __parse64BitString(self, data):
        d = unpack('<2L', data)
        return d[1] * 2 ** 32 + d[0]

    def __fileTimeToUnixTime(self, time):
        return int((time - 116444736000000000) / 10000000)

    def __knownGUIDs(self):
        guidMapping = {
            'ASF_Extended_Stream_Properties_Object'   : '14E6A5CB-C672-4332-8399-A96952065B5A',
            'ASF_Padding_Object'                      : '1806D474-CADF-4509-A4BA-9AABCB96AAE8',
            'ASF_Payload_Ext_Syst_Pixel_Aspect_Ratio' : '1B1EE554-F9EA-4BC8-821A-376B74E4C4B8',
            'ASF_Script_Command_Object'               : '1EFB1A30-0B62-11D0-A39B-00A0C90348F6',
            'ASF_No_Error_Correction'                 : '20FB5700-5B55-11CF-A8FD-00805F5C442B',
            'ASF_Content_Branding_Object'             : '2211B3FA-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Content_Encryption_Object'           : '2211B3FB-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Digital_Signature_Object'            : '2211B3FC-BD23-11D2-B4B7-00A0C955FC6E',
            'ASF_Extended_Content_Encryption_Object'  : '298AE614-2622-4C17-B935-DAE07EE9289C',
            'ASF_Simple_Index_Object'                 : '33000890-E5B1-11CF-89F4-00A0C90349CB',
            'ASF_Degradable_JPEG_Media'               : '35907DE0-E415-11CF-A917-00805F5C442B',
            'ASF_Payload_Extension_System_Timecode'   : '399595EC-8667-4E2D-8FDB-98814CE76C1E',
            'ASF_Binary_Media'                        : '3AFB65E2-47EF-40F2-AC2C-70A90D71D343',
            'ASF_Timecode_Index_Object'               : '3CB73FD0-0C4A-4803-953D-EDF7B6228F0C',
            'ASF_Metadata_Library_Object'             : '44231C94-9498-49D1-A141-1D134E457054',
            'ASF_Reserved_3'                          : '4B1ACBE3-100B-11D0-A39B-00A0C90348F6',
            'ASF_Reserved_4'                          : '4CFEDB20-75F6-11CF-9C0F-00A0C90349CB',
            'ASF_Command_Media'                       : '59DACFC0-59E6-11D0-A3AC-00A0C90348F6',
            'ASF_Header_Extension_Object'             : '5FBF03B5-A92E-11CF-8EE3-00C00C205365',
            'ASF_Media_Object_Index_Parameters_Obj'   : '6B203BAD-3F11-4E84-ACA8-D7613DE2CFA7',
            'ASF_Header_Object'                       : '75B22630-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Content_Description_Object'          : '75B22633-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Error_Correction_Object'             : '75B22635-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Data_Object'                         : '75B22636-668E-11CF-A6D9-00AA0062CE6C',
            'ASF_Web_Stream_Media_Subtype'            : '776257D4-C627-41CB-8F81-7AC7FF1C40CC',
            'ASF_Stream_Bitrate_Properties_Object'    : '7BF875CE-468D-11D1-8D82-006097C9A2B2',
            'ASF_Language_List_Object'                : '7C4346A9-EFE0-4BFC-B229-393EDE415C85',
            'ASF_Codec_List_Object'                   : '86D15240-311D-11D0-A3A4-00A0C90348F6',
            'ASF_Reserved_2'                          : '86D15241-311D-11D0-A3A4-00A0C90348F6',
            'ASF_File_Properties_Object'              : '8CABDCA1-A947-11CF-8EE4-00C00C205365',
            'ASF_File_Transfer_Media'                 : '91BD222C-F21C-497A-8B6D-5AA86BFC0185',
            'ASF_Advanced_Mutual_Exclusion_Object'    : 'A08649CF-4775-4670-8A16-6E35357566CD',
            'ASF_Bandwidth_Sharing_Object'            : 'A69609E6-517B-11D2-B6AF-00C04FD908E9',
            'ASF_Reserved_1'                          : 'ABD3D211-A9BA-11CF-8EE6-00C00C205365',
            'ASF_Bandwidth_Sharing_Exclusive'         : 'AF6060AA-5197-11D2-B6AF-00C04FD908E9',
            'ASF_Bandwidth_Sharing_Partial'           : 'AF6060AB-5197-11D2-B6AF-00C04FD908E9',
            'ASF_JFIF_Media'                          : 'B61BE100-5B4E-11CF-A8FD-00805F5C442B',
            'ASF_Stream_Properties_Object'            : 'B7DC0791-A9B7-11CF-8EE6-00C00C205365',
            'ASF_Video_Media'                         : 'BC19EFC0-5B4D-11CF-A8FD-00805F5C442B',
            'ASF_Audio_Spread'                        : 'BFC3CD50-618F-11CF-8BB2-00AA00B4E220',
            'ASF_Metadata_Object'                     : 'C5F8CBEA-5BAF-4877-8467-AA8C44FA4CCA',
            'ASF_Payload_Ext_Syst_Sample_Duration'    : 'C6BD9450-867F-4907-83A3-C77921B733AD',
            'ASF_Group_Mutual_Exclusion_Object'       : 'D1465A40-5A79-4338-B71B-E36B8FD6C249',
            'ASF_Extended_Content_Description_Object' : 'D2D0A440-E307-11D2-97F0-00A0C95EA850',
            'ASF_Stream_Prioritization_Object'        : 'D4FED15B-88D3-454F-81F0-ED5C45999E24',
            'ASF_Payload_Ext_System_Content_Type'     : 'D590DC20-07BC-436C-9CF7-F3BBFBF1A4DC',
            'ASF_Index_Object'                        : 'D6E229D3-35DA-11D1-9034-00A0C90349BE',
            'ASF_Bitrate_Mutual_Exclusion_Object'     : 'D6E229DC-35DA-11D1-9034-00A0C90349BE',
            'ASF_Index_Parameters_Object'             : 'D6E229DF-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Language'                      : 'D6E22A00-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Bitrate'                       : 'D6E22A01-35DA-11D1-9034-00A0C90349BE',
            'ASF_Mutex_Unknown'                       : 'D6E22A02-35DA-11D1-9034-00A0C90349BE',
            'ASF_Web_Stream_Format'                   : 'DA1E6B13-8359-4050-B398-388E965BF00C',
            'ASF_Payload_Ext_System_File_Name'        : 'E165EC0E-19ED-45D7-B4A7-25CBD1E28E9B',
            'ASF_Marker_Object'                       : 'F487CD01-A951-11CF-8EE6-00C00C205365',
            'ASF_Timecode_Index_Parameters_Object'    : 'F55E496D-9797-4B5D-8C8B-604DFE9BFB24',
            'ASF_Audio_Media'                         : 'F8699E40-5B4D-11CF-A8FD-00805F5C442B',
            'ASF_Media_Object_Index_Object'           : 'FEB103F8-12AD-4C64-840F-2A1D2F7AD48C',
            'ASF_Alt_Extended_Content_Encryption_Obj' : 'FF889EF1-ADEE-40DA-9E71-98704BB928CE',
        }
        return guidMapping

if __name__ == '__main__':
    import sys
    foo = WmaInfo(sys.argv[1])
    print "### Info: ###\n"
    foo.printinfo()
    print
    print "### Tags: ###\n"
    foo.printtags()
    print
    print "### Objects ###\n"
    foo.printobjects()
    sys.exit(0)

